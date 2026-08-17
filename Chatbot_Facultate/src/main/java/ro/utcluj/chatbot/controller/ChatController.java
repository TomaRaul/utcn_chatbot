package ro.utcluj.chatbot.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.*;
import ro.utcluj.chatbot.model.*;
import ro.utcluj.chatbot.repository.ConversationRepository;
import ro.utcluj.chatbot.repository.FeedbackRepository;
import ro.utcluj.chatbot.repository.KnowledgeRepository;
import ro.utcluj.chatbot.repository.MessageChunkRepository;
import ro.utcluj.chatbot.repository.MessageRepository;
import ro.utcluj.chatbot.service.OllamaService;
import ro.utcluj.chatbot.service.RagResult;
import ro.utcluj.chatbot.service.RagService;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/chat")
@CrossOrigin(origins = "*")
public class ChatController {

    private static final double FEEDBACK_BOOST_DELTA = 0.05;
    private static final double FEEDBACK_PENALTY_DELTA = -0.05;

    private static final int SUMMARY_TRIGGER_MESSAGES = 5;

    private final OllamaService ollamaService;
    private final RagService ragService;
    private final ConversationRepository conversationRepository;
    private final MessageRepository messageRepository;
    private final FeedbackRepository feedbackRepository;
    private final MessageChunkRepository messageChunkRepository;
    private final KnowledgeRepository knowledgeRepository;
    private final RestTemplate restTemplate = new RestTemplate();

    private static final String AUTH_VALIDATE_URL = "http://localhost:8081/auth/validate";

    public ChatController(OllamaService ollamaService,
                          RagService ragService,
                          ConversationRepository conversationRepository,
                          MessageRepository messageRepository,
                          FeedbackRepository feedbackRepository,
                          MessageChunkRepository messageChunkRepository,
                          KnowledgeRepository knowledgeRepository) {
        this.ollamaService = ollamaService;
        this.ragService = ragService;
        this.conversationRepository = conversationRepository;
        this.messageRepository = messageRepository;
        this.feedbackRepository = feedbackRepository;
        this.messageChunkRepository = messageChunkRepository;
        this.knowledgeRepository = knowledgeRepository;
    }

    private String extractUsername(String authHeader) {
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.set("Authorization", authHeader);
            HttpEntity<Void> entity = new HttpEntity<>(headers);
            ResponseEntity<Map> response = restTemplate.exchange(AUTH_VALIDATE_URL, HttpMethod.GET, entity, Map.class);
            if (response.getBody() != null && Boolean.TRUE.equals(response.getBody().get("valid"))) {
                return (String) response.getBody().get("username");
            }
        } catch (Exception e) {
            return null;
        }
        return null;
    }

    @PostMapping
    public ResponseEntity<?> chat(@RequestBody ChatRequest request,
                                   @RequestHeader("Authorization") String authHeader) {
        String username = extractUsername(authHeader);
        if (username == null) {
            return ResponseEntity.status(401).body(Map.of("error", "Neautorizat."));
        }

        Conversation conversation;
        if (request.getConversationId() != null) {
            conversation = conversationRepository.findById(request.getConversationId())
                    .filter(c -> username.equals(c.getUsername()))
                    .orElseGet(() -> createNewConversation(username));
        } else {
            conversation = createNewConversation(username);
        }

        List<Message> history = messageRepository.findByConversationIdOrderByCreatedAtAsc(conversation.getId());

        Long summarizedUntil = conversation.getSummarizedUntilMessageId();
        List<Message> recentHistory = summarizedUntil == null
                ? history
                : history.stream().filter(m -> m.getId() > summarizedUntil).toList();

        RagResult rag = ragService.findContext(request.getMessage(), recentHistory);
        String reply = ollamaService.chat(recentHistory, request.getMessage(),
                rag.getContext(), conversation.getSummary());

        Message userMessage = new Message();
        userMessage.setConversation(conversation);
        userMessage.setRole("user");
        userMessage.setContent(request.getMessage());
        messageRepository.save(userMessage);

        Message assistantMessage = new Message();
        assistantMessage.setConversation(conversation);
        assistantMessage.setRole("assistant");
        assistantMessage.setContent(reply);
        Message savedAssistant = messageRepository.save(assistantMessage);

        for (Long chunkId : rag.getChunkIds()) {
            Double score = rag.getChunkScores().get(chunkId);
            messageChunkRepository.save(new MessageChunk(savedAssistant.getId(), chunkId, score));
        }

        List<Message> unsummarized = new ArrayList<>(recentHistory);
        unsummarized.add(userMessage);
        unsummarized.add(savedAssistant);
        if (unsummarized.size() >= SUMMARY_TRIGGER_MESSAGES) {
            String newSummary = ollamaService.summarize(conversation.getSummary(), unsummarized);
            if (newSummary != null && !newSummary.isBlank()) {
                conversation.setSummary(newSummary);
                conversation.setSummarizedUntilMessageId(savedAssistant.getId());
                conversationRepository.save(conversation);
            }
        }

        if (conversation.getTitle() == null) {
            String title = request.getMessage().length() > 50
                    ? request.getMessage().substring(0, 50) + "..."
                    : request.getMessage();
            conversation.setTitle(title);
            conversationRepository.save(conversation);
        }

        return ResponseEntity.ok(new ChatResponse(reply, conversation.getId(), savedAssistant.getId()));
    }

    @GetMapping("/conversations")
    public ResponseEntity<?> getConversations(@RequestHeader("Authorization") String authHeader) {
        String username = extractUsername(authHeader);
        if (username == null) {
            return ResponseEntity.status(401).body(Map.of("error", "Neautorizat."));
        }
        return ResponseEntity.ok(conversationRepository.findByUsernameOrderByPinnedDescCreatedAtDesc(username));
    }

    @PatchMapping("/conversations/{id}/pin")
    public ResponseEntity<?> togglePin(@PathVariable Long id,
                                        @RequestBody(required = false) Map<String, Object> body,
                                        @RequestHeader("Authorization") String authHeader) {
        String username = extractUsername(authHeader);
        if (username == null) {
            return ResponseEntity.status(401).body(Map.of("error", "Neautorizat."));
        }
        Optional<Conversation> opt = conversationRepository.findById(id);
        if (opt.isEmpty() || !username.equals(opt.get().getUsername())) {
            return ResponseEntity.status(404).body(Map.of("error", "Conversatie inexistenta."));
        }
        Conversation conv = opt.get();
        boolean pinned;
        if (body != null && body.get("pinned") instanceof Boolean b) {
            pinned = b;
        } else {
            pinned = !conv.isPinned();
        }
        conv.setPinned(pinned);
        conversationRepository.save(conv);
        return ResponseEntity.ok(Map.of("ok", true, "pinned", pinned));
    }

    @DeleteMapping("/conversations/{id}")
    @Transactional
    public ResponseEntity<?> deleteConversation(@PathVariable Long id,
                                                 @RequestHeader("Authorization") String authHeader) {
        String username = extractUsername(authHeader);
        if (username == null) {
            return ResponseEntity.status(401).body(Map.of("error", "Neautorizat."));
        }
        Optional<Conversation> opt = conversationRepository.findById(id);
        if (opt.isEmpty() || !username.equals(opt.get().getUsername())) {
            return ResponseEntity.status(404).body(Map.of("error", "Conversatie inexistenta."));
        }
        List<Long> messageIds = messageRepository.findByConversationIdOrderByCreatedAtAsc(id)
                .stream().map(Message::getId).toList();
        if (!messageIds.isEmpty()) {
            messageChunkRepository.deleteByMessageIdIn(messageIds);
            feedbackRepository.deleteByMessageIdIn(messageIds);
        }
        conversationRepository.delete(opt.get());
        return ResponseEntity.ok(Map.of("ok", true));
    }

    @GetMapping("/conversations/{id}/messages")
    public ResponseEntity<?> getMessages(@PathVariable Long id,
                                          @RequestHeader("Authorization") String authHeader) {
        String username = extractUsername(authHeader);
        if (username == null) {
            return ResponseEntity.status(401).body(Map.of("error", "Neautorizat."));
        }
        return ResponseEntity.ok(messageRepository.findByConversationIdOrderByCreatedAtAsc(id));
    }

    @PostMapping("/feedback")
    public ResponseEntity<?> submitFeedback(@RequestBody Map<String, Object> body,
                                             @RequestHeader("Authorization") String authHeader) {
        String username = extractUsername(authHeader);
        if (username == null) {
            return ResponseEntity.status(401).body(Map.of("error", "Neautorizat."));
        }

        Long messageId = body.get("messageId") instanceof Number n ? n.longValue() : null;
        String rating = (String) body.get("rating");
        String correction = (String) body.get("correction");

        if (messageId == null || rating == null || (!rating.equals("up") && !rating.equals("down"))) {
            return ResponseEntity.badRequest().body(Map.of("error", "messageId si rating ('up'/'down') sunt obligatorii."));
        }

        Optional<Message> msgOpt = messageRepository.findById(messageId);
        if (msgOpt.isEmpty() || !"assistant".equals(msgOpt.get().getRole())) {
            return ResponseEntity.status(404).body(Map.of("error", "Mesaj inexistent."));
        }

        Feedback fb = new Feedback();
        fb.setMessageId(messageId);
        fb.setUsername(username);
        fb.setRating(rating);
        fb.setCorrection(correction);
        feedbackRepository.save(fb);

        double delta = "up".equals(rating) ? FEEDBACK_BOOST_DELTA : FEEDBACK_PENALTY_DELTA;
        List<MessageChunk> chunks = messageChunkRepository.findByMessageId(messageId);
        for (MessageChunk mc : chunks) {
            knowledgeRepository.adjustQualityScore(mc.getChunkId(), delta);
        }

        if ("down".equals(rating) && correction != null && !correction.isBlank()) {
            Message assistantMsg = msgOpt.get();
            List<Message> conv = messageRepository.findByConversationIdOrderByCreatedAtAsc(
                    assistantMsg.getConversation().getId());
            String userQuestion = findPrecedingUserQuestion(conv, messageId);

            KnowledgeEntry pending = new KnowledgeEntry();
            pending.setQuestion(userQuestion != null ? userQuestion : "(corecție utilizator)");
            pending.setAnswer(correction);
            pending.setSource("user-correction");
            pending.setChunkType("qna");
            pending.setStatus("pending");
            pending.setQualityScore(0.0);
            pending.setDerivedFromMessageId(messageId);
            knowledgeRepository.save(pending);
        }

        return ResponseEntity.ok(Map.of("ok", true));
    }

    private String findPrecedingUserQuestion(List<Message> conv, Long assistantMessageId) {
        for (int i = 0; i < conv.size(); i++) {
            if (assistantMessageId.equals(conv.get(i).getId())) {
                for (int j = i - 1; j >= 0; j--) {
                    if ("user".equals(conv.get(j).getRole())) {
                        return conv.get(j).getContent();
                    }
                }
            }
        }
        return null;
    }

    private Conversation createNewConversation(String username) {
        Conversation c = new Conversation();
        c.setUsername(username);
        return conversationRepository.save(c);
    }
}
