package ro.utcluj.auth_service.service;

import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class EmailService {

    private final JavaMailSender mailSender;

    @Value("${spring.mail.username}")
    private String fromAddress;

    public EmailService(JavaMailSender mailSender) {
        this.mailSender = mailSender;
    }

    public void sendVerificationCode(String to, String code) {
        SimpleMailMessage message = new SimpleMailMessage();
        message.setFrom(fromAddress);
        message.setTo(to);
        message.setSubject("Cod de verificare - Chatbot Facultate UTCN");
        message.setText(
                "Salut,\n\n" +
                "Codul tau de verificare pentru contul Chatbot Facultate este:\n\n" +
                "    " + code + "\n\n" +
                "Codul este valabil 10 minute.\n\n" +
                "Daca nu ai initiat tu inregistrarea, ignora acest mesaj.\n\n" +
                "-- Chatbot Facultate UTCN"
        );
        mailSender.send(message);
    }
}
