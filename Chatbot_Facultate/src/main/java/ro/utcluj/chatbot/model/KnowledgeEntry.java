package ro.utcluj.chatbot.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "knowledge_base")
public class KnowledgeEntry {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(columnDefinition = "TEXT", nullable = false)
    private String question;

    @Column(columnDefinition = "TEXT", nullable = false)
    private String answer;

    private String source;

    private LocalDateTime createdAt;

    @Column(columnDefinition = "TEXT")
    private String embedding;

    @Column(name = "chunk_type", length = 16)
    private String chunkType;

    @Column(length = 16)
    private String status;

    @Column(name = "quality_score")
    private Double qualityScore;

    @Column(name = "derived_from_message_id")
    private Long derivedFromMessageId;

    public Long getId() { return id; }
    public String getQuestion() { return question; }
    public String getAnswer() { return answer; }
    public String getSource() { return source; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public String getEmbedding() { return embedding; }
    public String getChunkType() { return chunkType; }
    public String getStatus() { return status; }
    public Double getQualityScore() { return qualityScore; }
    public Long getDerivedFromMessageId() { return derivedFromMessageId; }

    public void setQuestion(String question) { this.question = question; }
    public void setAnswer(String answer) { this.answer = answer; }
    public void setSource(String source) { this.source = source; }
    public void setEmbedding(String embedding) { this.embedding = embedding; }
    public void setChunkType(String chunkType) { this.chunkType = chunkType; }
    public void setStatus(String status) { this.status = status; }
    public void setQualityScore(Double qualityScore) { this.qualityScore = qualityScore; }
    public void setDerivedFromMessageId(Long derivedFromMessageId) { this.derivedFromMessageId = derivedFromMessageId; }
}
