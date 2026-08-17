package ro.utcluj.chatbot.model;

import jakarta.persistence.*;

@Entity
@Table(name = "message_chunks")
@IdClass(MessageChunkId.class)
public class MessageChunk {

    @Id
    @Column(name = "message_id")
    private Long messageId;

    @Id
    @Column(name = "chunk_id")
    private Long chunkId;

    @Column
    private Double score;

    public MessageChunk() {}

    public MessageChunk(Long messageId, Long chunkId, Double score) {
        this.messageId = messageId;
        this.chunkId = chunkId;
        this.score = score;
    }

    public Long getMessageId() { return messageId; }
    public void setMessageId(Long messageId) { this.messageId = messageId; }

    public Long getChunkId() { return chunkId; }
    public void setChunkId(Long chunkId) { this.chunkId = chunkId; }

    public Double getScore() { return score; }
    public void setScore(Double score) { this.score = score; }
}
