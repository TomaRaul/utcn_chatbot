package ro.utcluj.chatbot.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import ro.utcluj.chatbot.model.Message;

import java.util.List;

public interface MessageRepository extends JpaRepository<Message, Long> {
    List<Message> findByConversationIdOrderByCreatedAtAsc(Long conversationId);
}
