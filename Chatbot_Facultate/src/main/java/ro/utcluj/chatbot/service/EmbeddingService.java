package ro.utcluj.chatbot.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.*;

import java.util.Arrays;
import java.util.List;
import java.util.Map;

@Service
public class EmbeddingService {

    @Value("${ollama.base-url}")
    private String ollamaBaseUrl;

    @Value("${ollama.embedding-model:nomic-embed-text}")
    private String embeddingModel;

    private final RestTemplate restTemplate = new RestTemplate();

    public float[] embed(String text) {
        String url = ollamaBaseUrl + "/api/embeddings";

        Map<String, String> body = Map.of("model", embeddingModel, "prompt", text);
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        ResponseEntity<Map> response = restTemplate.postForEntity(
                url, new HttpEntity<>(body, headers), Map.class);

        if (response.getBody() == null || !response.getBody().containsKey("embedding")) {
            throw new RuntimeException("Ollama embedding response invalid");
        }

        List<Double> raw = (List<Double>) response.getBody().get("embedding");
        float[] result = new float[raw.size()];
        for (int i = 0; i < raw.size(); i++) {
            result[i] = raw.get(i).floatValue();
        }
        return result;
    }

    public String formatVector(float[] embedding) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < embedding.length; i++) {
            if (i > 0) sb.append(",");
            sb.append(embedding[i]);
        }
        sb.append("]");
        return sb.toString();
    }
}
