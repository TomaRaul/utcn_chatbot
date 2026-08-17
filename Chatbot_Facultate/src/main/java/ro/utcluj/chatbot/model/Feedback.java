package ro.utcluj.chatbot.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "feedback")
public class Feedback {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "message_id", nullable = false)
    private Long messageId;

    @Column(nullable = false)
    private String username;

    @Column(nullable = false, length = 16)
    private String rating;

    @Column(columnDefinition = "TEXT")
    private String correction;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @PrePersist
    public void prePersist() {
        this.createdAt = LocalDateTime.now();
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getMessageId() { return messageId; }
    public void setMessageId(Long messageId) { this.messageId = messageId; }

    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public String getRating() { return rating; }
    public void setRating(String rating) { this.rating = rating; }

    public String getCorrection() { return correction; }
    public void setCorrection(String correction) { this.correction = correction; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
