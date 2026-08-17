package ro.utcluj.chatbot.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.transaction.annotation.Transactional;
import ro.utcluj.chatbot.model.MessageChunk;
import ro.utcluj.chatbot.model.MessageChunkId;

import java.util.Collection;
import java.util.List;

public interface MessageChunkRepository extends JpaRepository<MessageChunk, MessageChunkId> {
    List<MessageChunk> findByMessageId(Long messageId);

    @Modifying
    @Transactional
    @Query("delete from MessageChunk mc where mc.messageId in :messageIds")
    void deleteByMessageIdIn(Collection<Long> messageIds);
}
