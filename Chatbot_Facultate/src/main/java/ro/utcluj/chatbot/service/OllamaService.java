package ro.utcluj.chatbot.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.*;
import ro.utcluj.chatbot.model.Message;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

@Service
public class OllamaService {

    @Value("${ollama.base-url}")
    private String ollamaBaseUrl;

    @Value("${ollama.model}")
    private String model;

    private static final String SYSTEM_PROMPT =
            "Ești un asistent virtual pentru Facultatea de Automatică și Calculatoare " +
            "din cadrul Universității Tehnice Cluj-Napoca (UTCN). " +
            "Răspunzi la întrebări legate de facultate, cursuri, profesori, " +
            "regulamente, orare, notare, cazare și proceduri universitare." +
            "\n\nReguli:" +
            "\n- Răspunde folosind informațiile din fragmentele furnizate. Extrage informația exactă cerută." +
            "\n- Nu inventa nume de profesori, cursuri, credite, ore, date sau alte detalii care nu apar în fragmente." +
            "\n- Fii scurt și precis — 1-3 propoziții, direct la subiect. Nu pune întrebări utilizatorului." +
            "\n- Răspunde doar în limba română." +
            "\n- Dacă utilizatorul folosește pronume (acesta, el, ea, acest profesor), referința e la subiectul discutat anterior." +
            "\n- Tratează ca sinonime: disciplină / curs / materie; profesor / cadru didactic / titular; " +
            "cazare / cămin / camin studențesc; email / mail / adresă de contact." +
            "\n- Dacă fragmentele conțin informație parțial relevantă (de exemplu date generale despre cazare " +
            "când se întreabă de cămin, sau un singur an de studiu), oferă acea informație în loc să refuzi." +
            "\n- Pentru o disciplină pot exista mai mulți titulari (curs, seminar, laborator). " +
            "Menționează-i pe toți doar dacă utilizatorul întreabă de ei." +
            "\n- Nu folosi paranteze drepte sau acolade ([X], {X}) ca placeholder în răspuns — " +
            "dacă nu ai valoarea concretă, spune că nu ai informația." +
            "\n- Doar dacă fragmentele nu conțin nimic legat de întrebare, răspunde: " +
            "\"Nu am informații despre asta în baza mea de date.\"";

    private static final String FALLBACK_REPLY = "Nu am informații despre asta în baza mea de date.";

    private static final String NAME_TOKEN = "[\\p{Lu}][\\p{Ll}]+(?:-[\\p{Lu}][\\p{Ll}]+)*";

    private static final Pattern NAME_AFTER_TITLE = Pattern.compile(
            "(?:Prof|Conf|Lect|Lector|As|Asist|Asistent|Şl|Șl|Dr)\\.?\\s+" +
            "(?:(?:univ|dr|ing|mat)\\.?\\s+)*" +
            "(" + NAME_TOKEN + "(?:\\s+" + NAME_TOKEN + "){0,4})",
            Pattern.UNICODE_CHARACTER_CLASS
    );

    private static final Pattern NAME_BEFORE_VERB = Pattern.compile(
            "(" + NAME_TOKEN + "(?:\\s+" + NAME_TOKEN + "){1,4})\\s+(?:predă|predau|ține|sus[țt]ine|conferen[țt]iaz[ăa])",
            Pattern.UNICODE_CHARACTER_CLASS
    );

    private static final Pattern NAME_AFTER_HONORIFIC = Pattern.compile(
            "(?i:doamna|domnul|dl\\.?|dna\\.?|lui)\\s+" +
            "(?:(?:Prof|Conf|Lect|Lector|As|Dr)\\.?\\s+)*" +
            "(?:(?:univ|dr|ing|mat)\\.?\\s+)*" +
            "(" + NAME_TOKEN + "(?:\\s+" + NAME_TOKEN + "){0,4})",
            Pattern.UNICODE_CHARACTER_CLASS
    );

    private static final Pattern STRIP_LEADING_NOISE = Pattern.compile(
            "^(?i:Doamna|Domnul|Dna|Dl|Disciplina|Universitatea|Facultatea|" +
            "Profesoara|Profesorul|Titularii|Titularul|Conform|Aceiași|Această|Acest)\\s+"
    );

    private final RestTemplate restTemplate = new RestTemplate();

    public String chat(List<Message> history, String userMessage, String ragContext, String conversationSummary) {
        String url = ollamaBaseUrl + "/api/chat";

        List<Map<String, String>> messages = new ArrayList<>();
        messages.add(Map.of("role", "system", "content", SYSTEM_PROMPT));

        messages.addAll(history.stream()
                .filter(m -> !("assistant".equals(m.getRole())
                        && m.getContent() != null
                        && m.getContent().startsWith("Nu am informații")))
                .map(m -> Map.of("role", m.getRole(), "content", m.getContent()))
                .collect(Collectors.toList()));

        String summaryBlock = (conversationSummary != null && !conversationSummary.isBlank())
                ? "Rezumatul conversației de până acum (context, nu sursă de adevăr factual):\n"
                  + conversationSummary + "\n\n"
                : "";

        String finalUserContent;
        if (ragContext != null && !ragContext.isBlank()) {
            finalUserContent = summaryBlock +
                    "<<FRAGMENTE_VERIFICATE>>\n" + ragContext + "\n<</FRAGMENTE_VERIFICATE>>\n\n" +
                    "Folosind informațiile dintre <<FRAGMENTE_VERIFICATE>>, " +
                    "răspunde la întrebarea de mai jos.\n\n" +
                    "Întrebare: " + userMessage;
        } else {
            finalUserContent = summaryBlock + userMessage;
        }
        messages.add(Map.of("role", "user", "content", finalUserContent));

        Map<String, Object> options = Map.of(
                "temperature", 0.0,
                "top_p", 0.5,
                "top_k", 20,
                "num_ctx", 8192,
                "repeat_penalty", 1.1,
                "seed", 42
        );

        Map<String, Object> requestBody = Map.of(
                "model", model,
                "messages", messages,
                "stream", false,
                "options", options
        );

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(requestBody, headers);

        ResponseEntity<Map> response = restTemplate.postForEntity(url, entity, Map.class);

        String reply = "Nu am putut genera un răspuns.";
        if (response.getBody() != null && response.getBody().containsKey("message")) {
            Map<String, String> messageObj = (Map<String, String>) response.getBody().get("message");
            reply = messageObj.get("content");
        }

        return validateGrounding(reply, ragContext);
    }

    private static final String SUMMARY_SYSTEM_PROMPT =
            "Ești un asistent care rezumă conversații dintre un student și chatbot-ul " +
            "Facultății de Automatică și Calculatoare UTCN. Primești un rezumat anterior " +
            "(opțional) și mesajele noi din conversație, și produci UN SINGUR rezumat " +
            "actualizat care le integrează pe amândouă." +
            "\nReguli:" +
            "\n- Păstrează informațiile concrete discutate: nume de profesori, discipline, " +
            "date, ore, credite, email-uri, precum și ce a întrebat și ce dorește studentul." +
            "\n- Elimină formulele de politețe și detaliile irelevante." +
            "\n- Scrie concis, în limba română, la persoana a treia, în cel mult 6-8 propoziții." +
            "\n- Nu inventa informații care nu apar în text." +
            "\n- Răspunde DOAR cu rezumatul, fără introduceri de tipul \"Iată rezumatul\".";

    public String summarize(String previousSummary, List<Message> messages) {
        String url = ollamaBaseUrl + "/api/chat";

        StringBuilder convo = new StringBuilder();
        if (previousSummary != null && !previousSummary.isBlank()) {
            convo.append("Rezumat anterior:\n").append(previousSummary).append("\n\n");
        }
        convo.append("Mesaje noi din conversație:\n");
        for (Message m : messages) {
            String who = "user".equals(m.getRole()) ? "Utilizator" : "Asistent";
            convo.append(who).append(": ").append(m.getContent()).append("\n");
        }
        convo.append("\nRezumatul actualizat:");

        List<Map<String, String>> chatMessages = new ArrayList<>();
        chatMessages.add(Map.of("role", "system", "content", SUMMARY_SYSTEM_PROMPT));
        chatMessages.add(Map.of("role", "user", "content", convo.toString()));

        Map<String, Object> options = Map.of(
                "temperature", 0.2,
                "num_ctx", 4096,
                "seed", 42
        );
        Map<String, Object> requestBody = Map.of(
                "model", model,
                "messages", chatMessages,
                "stream", false,
                "options", options
        );

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(requestBody, headers);

        try {
            ResponseEntity<Map> response = restTemplate.postForEntity(url, entity, Map.class);
            if (response.getBody() != null && response.getBody().containsKey("message")) {
                Map<String, String> messageObj = (Map<String, String>) response.getBody().get("message");
                String summary = messageObj.get("content");
                if (summary != null && !summary.isBlank()) {
                    return summary.trim();
                }
            }
        } catch (Exception e) {
            System.err.println("[summary] failed: " + e.getMessage());
        }
        return previousSummary;
    }

    String validateGrounding(String reply, String context) {
        if (reply == null || reply.isBlank()) return reply;
        if (context == null || context.isBlank()) return reply;

        if (normalize(reply).contains("nu am informa")) return reply;

        String normContext = normalize(context);
        Set<String> candidates = new LinkedHashSet<>();
        collectMatches(NAME_AFTER_TITLE.matcher(reply), candidates);
        collectMatches(NAME_BEFORE_VERB.matcher(reply), candidates);
        collectMatches(NAME_AFTER_HONORIFIC.matcher(reply), candidates);

        for (String candidate : candidates) {
            String stripped = STRIP_LEADING_NOISE.matcher(candidate).replaceAll("").trim();

            if (stripped.split("\\s+").length < 2) continue;
            String normCand = normalize(stripped);
            if (normCand.isBlank()) continue;
            if (!containsAsPhrase(normContext, normCand) && !containsAllTokens(normContext, normCand)) {
                System.err.println("[grounding] rejected reply — candidate not in context: '" + stripped + "'");
                return FALLBACK_REPLY;
            }
        }
        return reply;
    }

    private static void collectMatches(Matcher m, Set<String> out) {
        while (m.find()) {
            String s = m.group(1);
            if (s != null) {
                String trimmed = s.trim();
                if (!trimmed.isEmpty()) out.add(trimmed);
            }
        }
    }

    private static String normalize(String text) {
        if (text == null) return "";
        String lower = text.toLowerCase();
        return Normalizer.normalize(lower, Normalizer.Form.NFD)
                .replaceAll("\\p{InCombiningDiacriticalMarks}+", "");
    }

    private static boolean containsAsPhrase(String haystack, String needle) {
        Pattern p = Pattern.compile("\\b" + Pattern.quote(needle) + "\\b");
        return p.matcher(haystack).find();
    }

    // În documente numele apar adesea în altă ordine decât în răspuns
    // (ex. "Popescu Ion" vs "Ion Popescu"), deci acceptăm și potrivirea token cu token.
    private static boolean containsAllTokens(String haystack, String needle) {
        for (String token : needle.split("\\s+")) {
            if (token.length() < 3) continue;
            if (!containsAsPhrase(haystack, token)) return false;
        }
        return true;
    }
}
