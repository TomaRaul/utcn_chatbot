package ro.utcluj.chatbot.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;
import ro.utcluj.chatbot.model.KnowledgeEntry;

import java.util.List;

public interface KnowledgeRepository extends JpaRepository<KnowledgeEntry, Long> {

    @Query(value = "SELECT * FROM knowledge_base WHERE embedding IS NOT NULL AND (status IS NULL OR status = 'active')", nativeQuery = true)
    List<KnowledgeEntry> findAllActiveWithEmbeddings();

    @Query(value = "SELECT COUNT(*) FROM knowledge_base WHERE embedding IS NOT NULL AND (status IS NULL OR status = 'active')", nativeQuery = true)
    long countActiveWithEmbeddings();

    @Query(value = "SELECT * FROM knowledge_base WHERE status = 'pending' ORDER BY created_at DESC", nativeQuery = true)
    List<KnowledgeEntry> findPending();

    @Modifying
    @Transactional
    @Query(value = "UPDATE knowledge_base SET quality_score = LEAST(GREATEST(COALESCE(quality_score, 0) + :delta, -0.3), 0.5) WHERE id = :id", nativeQuery = true)
    void adjustQualityScore(@Param("id") Long id, @Param("delta") double delta);
}
