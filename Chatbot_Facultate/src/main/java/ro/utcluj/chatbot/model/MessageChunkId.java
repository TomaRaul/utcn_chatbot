package ro.utcluj.chatbot.model;

import java.io.Serializable;
import java.util.Objects;

public class MessageChunkId implements Serializable {

    private Long messageId;
    private Long chunkId;

    public MessageChunkId() {}

    public MessageChunkId(Long messageId, Long chunkId) {
        this.messageId = messageId;
        this.chunkId = chunkId;
    }

    public Long getMessageId() { return messageId; }
    public void setMessageId(Long messageId) { this.messageId = messageId; }

    public Long getChunkId() { return chunkId; }
    public void setChunkId(Long chunkId) { this.chunkId = chunkId; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof MessageChunkId)) return false;
        MessageChunkId that = (MessageChunkId) o;
        return Objects.equals(messageId, that.messageId) && Objects.equals(chunkId, that.chunkId);
    }

    @Override
    public int hashCode() {
        return Objects.hash(messageId, chunkId);
    }
}
