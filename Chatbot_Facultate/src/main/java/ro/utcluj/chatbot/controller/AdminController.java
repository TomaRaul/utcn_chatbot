package ro.utcluj.chatbot.controller;

import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import ro.utcluj.chatbot.model.KnowledgeEntry;
import ro.utcluj.chatbot.repository.KnowledgeRepository;
import ro.utcluj.chatbot.service.EmbeddingService;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/admin")
@CrossOrigin(origins = "*")
public class AdminController {

    private static final String AUTH_VALIDATE_URL = "http://localhost:8081/auth/validate";

    private final KnowledgeRepository knowledgeRepository;
    private final EmbeddingService embeddingService;
    private final RestTemplate restTemplate = new RestTemplate();

    public AdminController(KnowledgeRepository knowledgeRepository, EmbeddingService embeddingService) {
        this.knowledgeRepository = knowledgeRepository;
        this.embeddingService = embeddingService;
    }

    private boolean isAdmin(String authHeader) {
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.set("Authorization", authHeader);
            HttpEntity<Void> entity = new HttpEntity<>(headers);
            ResponseEntity<Map> response = restTemplate.exchange(AUTH_VALIDATE_URL, HttpMethod.GET, entity, Map.class);
            if (response.getBody() == null || !Boolean.TRUE.equals(response.getBody().get("valid"))) {
                return false;
            }
            Object role = response.getBody().get("role");
            return "ADMIN".equals(role);
        } catch (Exception e) {
            return false;
        }
    }

    @GetMapping("/pending")
    public ResponseEntity<?> listPending(@RequestHeader("Authorization") String authHeader) {
        if (!isAdmin(authHeader)) {
            return ResponseEntity.status(403).body(Map.of("error", "Doar adminii pot vedea coada."));
        }
        return ResponseEntity.ok(knowledgeRepository.findPending());
    }

    @PostMapping("/pending/{id}/approve")
    public ResponseEntity<?> approve(@PathVariable Long id,
                                      @RequestHeader("Authorization") String authHeader,
                                      @RequestBody(required = false) Map<String, String> body) {
        if (!isAdmin(authHeader)) {
            return ResponseEntity.status(403).body(Map.of("error", "Doar adminii pot aproba."));
        }
        Optional<KnowledgeEntry> opt = knowledgeRepository.findById(id);
        if (opt.isEmpty() || !"pending".equals(opt.get().getStatus())) {
            return ResponseEntity.status(404).body(Map.of("error", "Intrare inexistenta sau deja procesata."));
        }
        KnowledgeEntry entry = opt.get();

        if (body != null) {
            if (body.get("question") != null) entry.setQuestion(body.get("question"));
            if (body.get("answer") != null) entry.setAnswer(body.get("answer"));
        }

        try {
            float[] emb = embeddingService.embed(entry.getQuestion() + " " + entry.getAnswer());
            entry.setEmbedding(embeddingService.formatVector(emb));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of("error", "Generarea embedding-ului a esuat: " + e.getMessage()));
        }
        entry.setStatus("active");
        knowledgeRepository.save(entry);
        return ResponseEntity.ok(Map.of("ok", true, "id", id));
    }

    @PostMapping("/pending/{id}/reject")
    public ResponseEntity<?> reject(@PathVariable Long id,
                                     @RequestHeader("Authorization") String authHeader) {
        if (!isAdmin(authHeader)) {
            return ResponseEntity.status(403).body(Map.of("error", "Doar adminii pot respinge."));
        }
        Optional<KnowledgeEntry> opt = knowledgeRepository.findById(id);
        if (opt.isEmpty()) {
            return ResponseEntity.status(404).body(Map.of("error", "Intrare inexistenta."));
        }
        KnowledgeEntry entry = opt.get();
        entry.setStatus("rejected");
        knowledgeRepository.save(entry);
        return ResponseEntity.ok(Map.of("ok", true));
    }
}
