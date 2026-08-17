package ro.utcluj.chatbot.model;

public class ChatResponse {
    private String message;
    private Long conversationId;
    private Long messageId;

    public ChatResponse() {}

    public ChatResponse(String message, Long conversationId, Long messageId) {
        this.message = message;
        this.conversationId = conversationId;
        this.messageId = messageId;
    }

    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }

    public Long getConversationId() { return conversationId; }
    public void setConversationId(Long conversationId) { this.conversationId = conversationId; }

    public Long getMessageId() { return messageId; }
    public void setMessageId(Long messageId) { this.messageId = messageId; }
}
