package ro.utcluj.chatbot.service;

import org.springframework.stereotype.Service;
import ro.utcluj.chatbot.model.KnowledgeEntry;
import ro.utcluj.chatbot.model.Message;
import ro.utcluj.chatbot.repository.KnowledgeRepository;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class RagService {

    private static final int TOP_K_DEFAULT = 8;
    private static final int TOP_K_HIGH_CONFIDENCE = 3;
    private static final double HIGH_CONFIDENCE_THRESHOLD = 0.85;
    private static final double SIMILARITY_THRESHOLD = 0.25;
    private static final double KEYWORD_BOOST_PER_MATCH = 0.07;
    private static final double KEYWORD_BOOST_MAX = 0.25;
    private static final double QNA_BOOST = 0.15;
    private static final double SOURCE_MATCH_BOOST = 0.30;
    private static final double EXACT_QUESTION_MATCH_BOOST = 0.60;
    private static final int HISTORY_TURNS_FOR_QUERY = 2;
    private static final int SELF_SUFFICIENT_KEYWORD_THRESHOLD = 2;

    private static final Set<String> STOPWORDS = Set.of(
            "care", "este", "sunt", "cine", "cand", "unde", "ce", "cum", "de", "la", "cu",
            "in", "pe", "si", "sau", "dar", "din", "pentru", "despre", "ai", "are",
            "fie", "fara", "spune", "imi", "tu", "tine",
            "vrea", "stii", "stie",
            "the", "what", "who", "where", "when", "how", "does",
            "facultate", "facultatea", "universitate", "universitatea"
    );

    private final KnowledgeRepository knowledgeRepository;
    private final EmbeddingService embeddingService;

    public RagService(KnowledgeRepository knowledgeRepository, EmbeddingService embeddingService) {
        this.knowledgeRepository = knowledgeRepository;
        this.embeddingService = embeddingService;
    }

    public RagResult findContext(String userMessage) {
        return findContext(userMessage, List.of());
    }

    public RagResult findContext(String userMessage, List<Message> history) {
        if (knowledgeRepository.countActiveWithEmbeddings() == 0) {
            return new RagResult("", List.of(), Map.of());
        }

        String searchQuery = buildSearchQuery(userMessage, history);
        float[] queryEmbedding = embeddingService.embed(searchQuery);
        List<KnowledgeEntry> all = knowledgeRepository.findAllActiveWithEmbeddings();
        Set<String> keywords = extractKeywords(searchQuery);
        Set<String> matchingSources = findMatchingSources(keywords, all);
        String normalizedQuery = normalizeForMatch(searchQuery);

        List<Object[]> scored = all.stream()
                .filter(e -> e.getEmbedding() != null)
                .map(e -> {
                    double cosine = cosineSimilarity(queryEmbedding, parseVector(e.getEmbedding()));
                    double keywordBoost = calculateKeywordBoost(keywords, e);
                    double qnaBoost = "qna".equals(e.getChunkType()) ? QNA_BOOST : 0;
                    double sourceBoost = matchingSources.contains(e.getSource()) ? SOURCE_MATCH_BOOST : 0;
                    double qualityBoost = e.getQualityScore() != null ? e.getQualityScore() : 0;
                    double exactBoost = (e.getQuestion() != null && !normalizedQuery.isEmpty()
                            && normalizedQuery.equals(normalizeForMatch(e.getQuestion())))
                            ? EXACT_QUESTION_MATCH_BOOST : 0;
                    double total = cosine + keywordBoost + qnaBoost + sourceBoost + qualityBoost + exactBoost;
                    return new Object[]{e, total, cosine};
                })
                .sorted(Comparator.comparingDouble(arr -> -((double) arr[1])))
                .toList();

        int topK = (!scored.isEmpty() && (double) scored.get(0)[2] >= HIGH_CONFIDENCE_THRESHOLD)
                ? TOP_K_HIGH_CONFIDENCE
                : TOP_K_DEFAULT;

        List<Object[]> top = scored.stream()
                .filter(arr -> (double) arr[1] >= SIMILARITY_THRESHOLD)
                .limit(topK)
                .collect(Collectors.toList());

        if (top.isEmpty() && !scored.isEmpty()) {
            top = scored.stream().limit(3).collect(Collectors.toList());
        }

        if (top.isEmpty()) {
            return new RagResult("", List.of(), Map.of());
        }

        StringBuilder context = new StringBuilder();
        context.append("Informații relevante din documentele Facultății de Automatică și Calculatoare UTCN:\n\n");
        List<Long> chunkIds = new ArrayList<>();
        Map<Long, Double> chunkScores = new LinkedHashMap<>();
        int idx = 1;
        for (Object[] arr : top) {
            KnowledgeEntry entry = (KnowledgeEntry) arr[0];
            double score = (double) arr[1];
            chunkIds.add(entry.getId());
            chunkScores.put(entry.getId(), score);
            context.append("--- Fragment ").append(idx).append(" ");
            if (entry.getSource() != null) {
                context.append("(Sursă: ").append(entry.getSource()).append(") ");
            }
            context.append("---\n");
            if (entry.getQuestion() != null && !entry.getQuestion().isBlank()) {
                context.append("Întrebare: ").append(entry.getQuestion()).append("\n");
                context.append("Răspuns: ").append(entry.getAnswer()).append("\n\n");
            } else {
                context.append(entry.getAnswer()).append("\n\n");
            }
            idx++;
        }
        return new RagResult(context.toString().trim(), chunkIds, chunkScores);
    }

    public boolean hasRelevantContext(String userMessage) {
        return knowledgeRepository.countActiveWithEmbeddings() > 0;
    }

    private String buildSearchQuery(String userMessage, List<Message> history) {
        if (history == null || history.isEmpty()) {
            return userMessage;
        }

        if (extractKeywords(userMessage).size() >= SELF_SUFFICIENT_KEYWORD_THRESHOLD) {
            return userMessage;
        }
        List<String> recentUserTurns = new ArrayList<>();
        for (int i = history.size() - 1; i >= 0 && recentUserTurns.size() < HISTORY_TURNS_FOR_QUERY; i--) {
            Message m = history.get(i);
            if ("user".equals(m.getRole()) && m.getContent() != null && !m.getContent().isBlank()) {
                recentUserTurns.add(0, m.getContent());
            }
        }
        if (recentUserTurns.isEmpty()) {
            return userMessage;
        }
        return String.join(" ", recentUserTurns) + " " + userMessage;
    }

    private Set<String> extractKeywords(String text) {
        String normalized = normalize(text);
        return Arrays.stream(normalized.split("\\s+"))
                .map(s -> s.replaceAll("[^a-z0-9]", ""))
                .filter(s -> s.length() >= 3)
                .filter(s -> !STOPWORDS.contains(s))
                .collect(Collectors.toSet());
    }

    private double calculateKeywordBoost(Set<String> queryKeywords, KnowledgeEntry entry) {
        if (queryKeywords.isEmpty()) return 0;
        String haystack = normalize(entry.getQuestion() + " " + entry.getAnswer());
        long matches = queryKeywords.stream().filter(haystack::contains).count();
        return Math.min(matches * KEYWORD_BOOST_PER_MATCH, KEYWORD_BOOST_MAX);
    }

    private Set<String> findMatchingSources(Set<String> queryKeywords, List<KnowledgeEntry> entries) {
        if (queryKeywords.isEmpty()) return Collections.emptySet();
        Map<String, Set<String>> sourceTokens = new HashMap<>();
        for (KnowledgeEntry e : entries) {
            String src = e.getSource();
            if (src == null) continue;
            sourceTokens.computeIfAbsent(src, this::tokenizeSource);
        }
        Set<String> matching = new HashSet<>();
        for (Map.Entry<String, Set<String>> entry : sourceTokens.entrySet()) {
            Set<String> tokens = entry.getValue();
            if (tokens.isEmpty()) continue;
            if (!Collections.disjoint(tokens, queryKeywords)) {
                matching.add(entry.getKey());
            }
        }
        return matching;
    }

    private Set<String> tokenizeSource(String source) {
        if (source == null) return Collections.emptySet();
        String stem = source.replaceAll("\\.[^.]+$", "");
        String split = stem.replaceAll("([a-z])([A-Z])", "$1 $2")
                           .replaceAll("([A-Z]+)([A-Z][a-z])", "$1 $2")
                           .replaceAll("[_\\d]", " ");
        Set<String> tokens = new HashSet<>();
        for (String tok : split.split("\\s+")) {
            String n = normalize(tok).replaceAll("[^a-z0-9]", "");
            if (n.length() >= 4) tokens.add(n);
        }
        return tokens;
    }

    private String normalizeForMatch(String text) {
        return normalize(text).replaceAll("[^a-z0-9]+", " ").trim();
    }

    private String normalize(String text) {
        if (text == null) return "";
        String lower = text.toLowerCase();
        String stripped = Normalizer.normalize(lower, Normalizer.Form.NFD)
                .replaceAll("\\p{InCombiningDiacriticalMarks}+", "");
        return stripped;
    }

    private float[] parseVector(String vectorJson) {
        String trimmed = vectorJson.trim().replaceAll("[\\[\\]]", "");
        String[] parts = trimmed.split(",");
        float[] result = new float[parts.length];
        for (int i = 0; i < parts.length; i++) {
            result[i] = Float.parseFloat(parts[i].trim());
        }
        return result;
    }

    private double cosineSimilarity(float[] a, float[] b) {
        if (a.length != b.length) return 0;
        double dot = 0, normA = 0, normB = 0;
        for (int i = 0; i < a.length; i++) {
            dot += a[i] * b[i];
            normA += a[i] * a[i];
            normB += b[i] * b[i];
        }
        if (normA == 0 || normB == 0) return 0;
        return dot / (Math.sqrt(normA) * Math.sqrt(normB));
    }
}
