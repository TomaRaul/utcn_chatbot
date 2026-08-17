package ro.utcluj.auth_service.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;
import ro.utcluj.auth_service.dto.AuthRequest;
import ro.utcluj.auth_service.dto.AuthResponse;
import ro.utcluj.auth_service.model.User;
import ro.utcluj.auth_service.repository.UserRepository;
import ro.utcluj.auth_service.service.EmailService;
import ro.utcluj.auth_service.util.JwtUtil;

import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/auth")
@CrossOrigin(origins = "*")
public class AuthController {

    private static final SecureRandom RANDOM = new SecureRandom();

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtUtil jwtUtil;
    private final EmailService emailService;

    @Value("${verification.code.expiration.minutes}")
    private long codeExpirationMinutes;

    public AuthController(UserRepository userRepository,
                          PasswordEncoder passwordEncoder,
                          JwtUtil jwtUtil,
                          EmailService emailService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtUtil = jwtUtil;
        this.emailService = emailService;
    }

    @PostMapping("/register")
    public ResponseEntity<?> register(@RequestBody AuthRequest request) {
        if (request.getEmail() == null || request.getEmail().isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "Adresa de email este obligatorie."));
        }
        if (userRepository.existsByUsername(request.getUsername())) {
            return ResponseEntity.badRequest().body(Map.of("error", "Username-ul este deja folosit."));
        }
        if (userRepository.existsByEmail(request.getEmail())) {
            return ResponseEntity.badRequest().body(Map.of("error", "Acest email este deja inregistrat."));
        }

        String code = generateCode();
        User user = new User();
        user.setUsername(request.getUsername());
        user.setEmail(request.getEmail());
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setRole("USER");
        user.setVerified(false);
        user.setVerificationCode(code);
        user.setCodeExpiresAt(LocalDateTime.now().plusMinutes(codeExpirationMinutes));
        userRepository.save(user);

        try {
            emailService.sendVerificationCode(request.getEmail(), code);
        } catch (Exception e) {
            userRepository.delete(user);
            return ResponseEntity.status(500).body(Map.of(
                    "error", "Nu s-a putut trimite emailul de verificare. Verifica adresa si incearca din nou."
            ));
        }

        return ResponseEntity.ok(Map.of(
                "message", "Cod de verificare trimis pe email.",
                "username", user.getUsername(),
                "email", user.getEmail()
        ));
    }

    @PostMapping("/verify")
    public ResponseEntity<?> verify(@RequestBody AuthRequest request) {
        Optional<User> userOpt = userRepository.findByUsername(request.getUsername());
        if (userOpt.isEmpty()) {
            return ResponseEntity.status(404).body(Map.of("error", "Utilizatorul nu exista."));
        }

        User user = userOpt.get();
        if (user.isVerified()) {
            return ResponseEntity.badRequest().body(Map.of("error", "Contul este deja verificat."));
        }
        if (user.getVerificationCode() == null || user.getCodeExpiresAt() == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "Niciun cod activ. Cere un cod nou."));
        }
        if (LocalDateTime.now().isAfter(user.getCodeExpiresAt())) {
            return ResponseEntity.badRequest().body(Map.of("error", "Codul a expirat. Cere un cod nou."));
        }
        if (!user.getVerificationCode().equals(request.getCode())) {
            return ResponseEntity.badRequest().body(Map.of("error", "Cod invalid."));
        }

        user.setVerified(true);
        user.setVerificationCode(null);
        user.setCodeExpiresAt(null);
        userRepository.save(user);

        String token = jwtUtil.generateToken(user.getUsername(), user.getRole());
        return ResponseEntity.ok(new AuthResponse(token, user.getUsername(), user.getRole()));
    }

    @PostMapping("/resend")
    public ResponseEntity<?> resend(@RequestBody AuthRequest request) {
        Optional<User> userOpt = userRepository.findByUsername(request.getUsername());
        if (userOpt.isEmpty()) {
            return ResponseEntity.status(404).body(Map.of("error", "Utilizatorul nu exista."));
        }
        User user = userOpt.get();
        if (user.isVerified()) {
            return ResponseEntity.badRequest().body(Map.of("error", "Contul este deja verificat."));
        }

        String code = generateCode();
        user.setVerificationCode(code);
        user.setCodeExpiresAt(LocalDateTime.now().plusMinutes(codeExpirationMinutes));
        userRepository.save(user);

        try {
            emailService.sendVerificationCode(user.getEmail(), code);
        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of("error", "Nu s-a putut trimite emailul."));
        }
        return ResponseEntity.ok(Map.of("message", "Cod nou trimis pe email."));
    }

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody AuthRequest request) {
        Optional<User> userOpt = userRepository.findByUsername(request.getUsername());

        if (userOpt.isEmpty() || !passwordEncoder.matches(request.getPassword(), userOpt.get().getPassword())) {
            return ResponseEntity.status(401).body(Map.of("error", "Username sau parola incorecte."));
        }

        User user = userOpt.get();
        if (!user.isVerified()) {
            return ResponseEntity.status(403).body(Map.of(
                    "error", "Contul nu este verificat. Verifica emailul.",
                    "requiresVerification", true,
                    "username", user.getUsername()
            ));
        }

        String token = jwtUtil.generateToken(user.getUsername(), user.getRole());
        return ResponseEntity.ok(new AuthResponse(token, user.getUsername(), user.getRole()));
    }

    @GetMapping("/validate")
    public ResponseEntity<?> validate(@RequestHeader("Authorization") String authHeader) {
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            return ResponseEntity.status(401).body(Map.of("valid", false));
        }

        String token = authHeader.substring(7);
        boolean valid = jwtUtil.validateToken(token);

        if (valid) {
            String username = jwtUtil.extractUsername(token);
            String role = jwtUtil.extractRole(token);
            return ResponseEntity.ok(Map.of(
                    "valid", true,
                    "username", username,
                    "role", role != null ? role : "USER"
            ));
        }

        return ResponseEntity.status(401).body(Map.of("valid", false));
    }

    private String generateCode() {
        int n = RANDOM.nextInt(1_000_000);
        return String.format("%06d", n);
    }
}
