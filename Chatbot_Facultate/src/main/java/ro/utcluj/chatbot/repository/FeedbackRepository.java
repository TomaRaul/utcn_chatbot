package ro.utcluj.chatbot.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.transaction.annotation.Transactional;
import ro.utcluj.chatbot.model.Feedback;

import java.util.Collection;
import java.util.List;

public interface FeedbackRepository extends JpaRepository<Feedback, Long> {
    List<Feedback> findByMessageId(Long messageId);

    @Modifying
    @Transactional
    @Query("delete from Feedback f where f.messageId in :messageIds")
    void deleteByMessageIdIn(Collection<Long> messageIds);
}
