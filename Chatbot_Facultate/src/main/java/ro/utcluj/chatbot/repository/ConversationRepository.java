package ro.utcluj.chatbot.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import ro.utcluj.chatbot.model.Conversation;

import java.util.List;

public interface ConversationRepository extends JpaRepository<Conversation, Long> {
    List<Conversation> findByUsernameOrderByPinnedDescCreatedAtDesc(String username);
}
