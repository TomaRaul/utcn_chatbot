package ro.utcluj.chatbot.service;

import java.util.List;
import java.util.Map;

public class RagResult {
    private final String context;
    private final List<Long> chunkIds;
    private final Map<Long, Double> chunkScores;

    public RagResult(String context, List<Long> chunkIds, Map<Long, Double> chunkScores) {
        this.context = context;
        this.chunkIds = chunkIds;
        this.chunkScores = chunkScores;
    }

    public String getContext() { return context; }
    public List<Long> getChunkIds() { return chunkIds; }
    public Map<Long, Double> getChunkScores() { return chunkScores; }
}
