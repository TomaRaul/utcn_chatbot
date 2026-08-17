import os
import sys
import requests
import psycopg2
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "chatbot_db",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", "")
}

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"

SOURCE = "INFO UTILE CAZARE UTCN.pdf"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def get_embedding(text):
    r = requests.post(OLLAMA_URL, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=120)
    r.raise_for_status()
    return r.json()["embedding"]

def format_vector(emb):
    return "[" + ",".join(map(str, emb)) + "]"

def build_cazare_qna():
    pairs = []

    def add(q, a):
        pairs.append((q, a))

    add(
        "Când are loc cazarea în cămine la UTCN?",
        "Cazarea studenților în căminele UTCN pentru anul universitar 2025-2026 se face în perioada "
        "23-26 septembrie 2025, conform Calendarului cazărilor pentru început de an universitar 2025-2026."
    )

    add(
        "Care este programul de cazare pe zile la UTCN?",
        "Calendarul cazărilor la UTCN pentru anul universitar 2025-2026 este:\n"
        "• 23.09.2025 (prima zi): orele 08-18 — studenții de anul I licență.\n"
        "• 24.09.2025 (a doua zi): orele 08-20 — studenții la master, căsătoriți, doctoranzi, "
        "angajați tineri, anul VI și anul V Arhitectură, studenții anul IV, III, II licență. "
        "Se va respecta această ordine.\n"
        "• 25.09.2025 (a treia zi): orele 08-11 — studenții care nu s-au putut prezenta din motive obiective "
        "și au anunțat comisia de cazare din căminul repartizat; orele 13-18 — studenți cu drept de cazare "
        "în urma glisării listelor, în limita locurilor disponibile.\n"
        "• 26.09.2025 (a patra zi): orele 09-14 — studenți cu drept de cazare în urma unei noi glisări, "
        "în limita locurilor disponibile din ziua anterioară."
    )

    add(
        "Când se cazează studenții din anul 1 în cămine?",
        "Studenții de anul I licență se cazează în prima zi de cazare, pe 23.09.2025, "
        "în intervalul orar 08:00 - 18:00."
    )

    add(
        "Când se cazează studenții de la master?",
        "Studenții la master se cazează în a doua zi de cazare, pe 24.09.2025, "
        "în intervalul orar 08:00 - 20:00, împreună cu studenții căsătoriți, doctoranzi, "
        "angajați tineri, anul VI și V Arhitectură, și studenții din anii IV, III și II licență."
    )

    add(
        "Când se cazează studenții din anul 2, 3 sau 4?",
        "Studenții din anii II, III și IV licență se cazează pe 24.09.2025, "
        "în intervalul orar 08:00 - 20:00. Se respectă ordinea: master, căsătoriți, doctoranzi, "
        "angajați tineri, anul VI și V Arhitectură, apoi anul IV, III și II licență."
    )

    add(
        "Ce se întâmplă dacă nu mă pot prezenta la cazare în ziua programată?",
        "Studenții care nu s-au putut prezenta din motive obiective în zilele anterioare și au anunțat "
        "comisia de cazare din căminul în care au fost repartizați pot veni pe 25.09.2025, "
        "în intervalul orar 08:00 - 11:00. Dacă nu anunți comisia de cazare și nu te prezinți la data "
        "și ora fixată conform listelor publicate, pierzi dreptul de cazare."
    )

    add(
        "Care este programul comisiilor de cazare?",
        "Comisiile de cazare funcționează zilnic în perioada 23-26 septembrie 2025. "
        "Între orele 12:00 și 12:30, comisiile se vor afla în pauza de masă."
    )

    add(
        "Când se cazează studenții internaționali sau Erasmus?",
        "Studenții internaționali care fac parte din programul Erasmus, studenții în anul pregătitor "
        "și cei veniți prin mobilități au dreptul să se prezinte la cazare și să ocupe locurile "
        "rezervate acestora începând cu prima zi de cazare, 23.09.2025."
    )

    add(
        "Unde sunt cazați studenții internaționali din anul pregătitor?",
        "Studenții străini/internaționali din anul 1 pregătitor vor fi cazați pe locurile rezervate "
        "acestora în Căminul 2 Mărăști - Parter."
    )

    add(
        "Unde sunt cazați studenții Erasmus sau EUT+?",
        "Studenții veniți prin mobilități (de exemplu, Erasmus, EUT+, etc.) vor fi cazați pe locurile "
        "rezervate acestora în Căminul 1 Mărăști - Parter."
    )

    add(
        "Unde sunt cazați studenții internaționali care nu sunt în anul pregătitor?",
        "Studenții internaționali, alții decât cei din anul 1 pregătitor și studenții veniți prin "
        "mobilități (Erasmus, EUT+, etc.), vor fi repartizați în cămine pe baza listelor întocmite "
        "de facultăți, după ce Biroul de Relații Internaționale a transmis informațiile complete."
    )

    add(
        "Cum se face repartizarea studenților în cămine?",
        "Repartizarea studenților în căminele aferente facultăților, în perioada 23-26.09.2025, "
        "se face în funcție de numărul de locuri aprobate de Directorul General Administrativ "
        "și de listele întocmite de decanatele fiecărei facultăți."
    )

    add(
        "Unde pot vedea listele de cazare?",
        "Listele de cazare se afișează anterior pe site-urile fiecărei facultăți și se transmit "
        "comisiilor de cazare pe cămine, în format fizic, pentru punerea în aplicare."
    )

    add(
        "Cine se ocupă de procesul de cazare?",
        "Până la data de 29.09.2025, atribuțiile privind procesul de cazare pentru fiecare facultate "
        "revin comisiilor de cazare, ce au ca președinți prodecanii facultăților respective. "
        "Începând cu data de 30.09.2025, Direcția Generală Administrativă va prelua în integralitate "
        "toate atribuțiile legate de continuarea activității de cazare, preluarea cererilor de cazare, "
        "repartizarea locurilor din cămine, etc."
    )

    add(
        "Pot veni cu mașina la cazare în campusul Observator?",
        "Da, în campusul studențesc Observator se permite accesul cu autoturismele personale ale "
        "studenților și/sau a însoțitorilor acestora pentru cazare, în parcarea dinspre strada "
        "Observatorului, nr. 36, doar pentru descărcarea bagajelor. Retragerea autoturismelor din "
        "incintă este ulterior obligatorie."
    )

    add(
        "Există parcare în campusul Mărăști?",
        "Nu, în campusul din Mărăști al UTCN nu există posibilități de parcare în incintă."
    )

    add(
        "Pot veni cu mașina la cazare în Baia Mare?",
        "Da, în campusurile din Baia Mare, situate pe str. Victoriei, nr. 76 și str. Dr. Victor Babeș, "
        "nr. 62A, se permite accesul cu autoturismele personale ale studenților și/sau însoțitorilor "
        "acestora în limita disponibilității locurilor de parcare."
    )

    add(
        "Cum transport bagajele voluminoase la cămin?",
        "Pentru bagajele voluminoase (de exemplu, frigidere), administrația pune la dispoziția "
        "studenților cărucioare cu ajutorul cărora acestea pot fi transportate până la cămin."
    )

    add(
        "Pot veni cu părinții la cazare?",
        "Da, persoanele însoțitoare au acces până la intrarea în cămin, în incinta acestuia "
        "având drept de intrare doar studenții care se cazează. Există posibilitatea de a vizita "
        "camerele unde s-au cazat studenții, care au fost însoțiți, înainte cu 2 ore de încheierea "
        "procesului de cazare din ziua respectivă."
    )

    add(
        "Pot să rămân în cămin imediat după cazare?",
        "Da, după cazare, studenții pot opta să rămână în cămin, respectiv în camera repartizată "
        "la cazare, sau să se întoarcă în localitatea de domiciliu, până la data începerii anului "
        "universitar sau oricând doresc."
    )

    add(
        "Ce documente am nevoie pentru cazare la cămin?",
        "Pentru cazare, studenții înmatriculați la UTCN vor avea asupra lor următoarele documente:\n"
        "• Actul de identitate sau pașaportul.\n"
        "• Aviz epidemiologic eliberat de către medicul de familie sau de către medicul de la "
        "cabinetele medicale existente în campusurile studențești ale UTCN."
    )

    add(
        "Am nevoie de aviz epidemiologic pentru cazare?",
        "Da, pentru cazare la căminele UTCN este necesar un aviz epidemiologic eliberat de către "
        "medicul de familie sau de către medicul de la cabinetele medicale existente în campusurile "
        "studențești ale UTCN."
    )

    add(
        "Poate altcineva să mă cazeze în locul meu?",
        "Da, studenții se pot caza și printr-o persoană împuternicită, în baza unei procuri notariale. "
        "Cazarea se face numai personal, pe baza actului de identitate, sau prin împuternicire notarială."
    )

    add(
        "Când pierd dreptul de cazare la cămin?",
        "Studenții pierd dreptul de cazare dacă:\n"
        "• Nu se prezintă la data și ora fixată conform listelor publicate, fără a anunța în prealabil "
        "comisia de cazare.\n"
        "• Refuză locul repartizat pentru cazare.\n"
        "• Sunt excluși din cămin, în ultimele 12 luni sau pe toată perioada studiilor."
    )

    add(
        "Cum obțin gratuitate la cazare dacă sunt copil al unui angajat UTCN?",
        "Pentru gratuitate la cazare, în calitate de copii ai personalului aflat în activitate/pensionat "
        "din sistemul de învățământ, studenții vor depune la administratorul căminului unde sunt cazați "
        "(la data cazării) următoarele documente:\n"
        "• Cerere de gratuitate tipizată.\n"
        "• Copie după cartea de identitate.\n"
        "• Copie după certificatul de naștere.\n"
        "• Adeverință de salariu al părintelui/părinților.\n"
        "• Copii după alte acte, în cazuri speciale (de exemplu, sentința de divorț)."
    )

    add(
        "Cum obțin gratuitate la cazare dacă sunt orfan sau din familie monoparentală?",
        "Pentru gratuitate la cazare, în calitate de orfani de unul sau ambii părinți decedați, "
        "sau proveniți din familii monoparentale și grupuri defavorizate, studenții vor depune "
        "la data cazării următoarele documente:\n"
        "• Cerere de gratuitate tipizată.\n"
        "• Copie după cartea de identitate.\n"
        "• Copie după certificatul de naștere.\n"
        "• Copie după certificatul de deces / copie după sentința de divorț sau certificat de divorț / "
        "adeverința de celibat/adeverință pentru studenții proveniți din centrul de plasament."
    )

    add(
        "Care sunt etapele procesului de cazare la UTCN?",
        "Studenții care se prezintă la cazare vor parcurge următoarele etape:\n"
        "1. Verificarea listelor nominale cu studenții care au obținut dreptul de cazare "
        "(afișate în prealabil, pentru cazările de la începutul anului universitar).\n"
        "2. Încărcarea/preluarea unui selfie pe platforma me.utcluj.app (autentificare cu contul "
        "instituțional @student.utcluj.ro).\n"
        "3. Primirea validării pozei în format digital, pe baza confruntării datelor din actul de identitate.\n"
        "4. Semnarea în două exemplare a contractului de cazare/închiriere generat de aplicația digitală "
        "infra.utcluj.app. Un contract rămâne la student, celălalt la administrația căminului.\n"
        "5. Completarea cererii de stabilire a reședinței (dacă este cazul).\n"
        "6. Plata regiei de cămin și a abonamentului de masă (dacă este cazul).\n"
        "7. Primirea legitimației/cardului de cămin (format digital, în aplicația me.utcluj.app) "
        "după efectuarea plăților/semnării contractului.\n"
        "8. Primirea efectivelor de pat (saltea, pernă, pătură, lenjerie, etc.).\n"
        "9. Preluarea camerei, pe bază de proces-verbal de predare-primire."
    )

    add(
        "Unde îmi încarc poza pentru cazare?",
        "Poza (selfie) pentru cazare se încarcă pe platforma me.utcluj.app, "
        "folosind contul instituțional @student.utcluj.ro pentru autentificare. "
        "Poza va fi validată pe baza confruntării datelor din actul de identitate."
    )

    add(
        "Unde semnez contractul de cazare?",
        "Contractul de cazare/închiriere se generează și se semnează prin aplicația digitală de "
        "management a infrastructurii UTCN — infra.utcluj.app. Se semnează în două exemplare: "
        "un contract rămâne la studentul cazat, iar celălalt la administrația căminului."
    )

    add(
        "Cum primesc legitimația de cămin?",
        "Legitimația/cardul de cămin se primește în format digital, în aplicația me.utcluj.app, "
        "în urma efectuării plăților și semnării contractului de cazare."
    )

    add(
        "Ce primesc la cazare ca efecte de pat?",
        "La cazare, studenții primesc efectivele de pat: saltea, pernă, pătură, lenjerie, etc. "
        "Preluarea camerei se face pe bază de proces-verbal de predare-primire."
    )

    add(
        "Cât costă regia de cămin în prima lună?",
        "Regia de cămin pentru prima lună se achită la cazare, la aceasta adăugându-se o sumă "
        "nereturnabilă de 100 lei, obligatorie în prima lună de cazare pentru toți studenții, "
        "indiferent de forma de învățământ sau anii de studiu (inclusiv studenții care beneficiază "
        "de reduceri sau gratuități)."
    )

    add(
        "Ce este suma de 100 lei la cazare?",
        "Suma de 100 lei este o taxă nereturnabilă care se achită la cazare, în prima lună de cazare, "
        "de toți studenții, indiferent de forma de învățământ sau anii de studiu. Aceasta se adaugă "
        "la regia de cămin. Inclusiv studenții care beneficiază de reduceri sau gratuități trebuie "
        "să achite această sumă."
    )

    add(
        "Ce este websinu.utcluj.ro și de ce contează pentru cazare?",
        "websinu.utcluj.ro este Sistemul Informatic Studenți, gestionat de secretariatele facultăților. "
        "Cazarea în căminele UTCN este condiționată de prezența datelor personale ale studentului în acest "
        "sistem. Adăugarea/corectarea datelor se face la Secretariatele Facultăților (pentru studenți, "
        "inclusiv studenți internaționali, în mobilitate sau în an pregătitor)."
    )

    add(
        "Ce este emsys.utcluj.app?",
        "emsys.utcluj.app este Sistemul de Management Activitate și Angajați, gestionat de Direcția "
        "Resurse Umane. Pentru angajații UTCN, cazarea este condiționată de prezența datelor personale "
        "în acest sistem. Adăugarea/corectarea datelor se face la Direcția Resurse Umane."
    )

    add(
        "Ce este me.utcluj.app?",
        "me.utcluj.app este platforma de interacțiune cu infrastructura și facilitățile puse la "
        "dispoziție de UTCN. Se folosește pentru: încărcarea selfie-ului necesar la cazare "
        "(autentificare cu @student.utcluj.ro), primirea legitimației/cardului de cămin în format "
        "digital și alte servicii studențești. Link: https://me.utcluj.app/"
    )

    add(
        "Ce este infra.utcluj.app?",
        "infra.utcluj.app este aplicația digitală de management al infrastructurii UTCN, folosită "
        "pentru generarea și semnarea contractului de cazare/închiriere în căminele UTCN."
    )

    add(
        "Cum intru în cămin pe parcursul anului universitar?",
        "La intrarea în campus/cămin, studentul trebuie să prezinte legitimația de cămin eliberată de "
        "comisia de cazare, care atestă calitatea de chiriaș al UTCN. Legitimația se poate prezenta "
        "în format fizic (imprimată pe un suport material) sau electronic (imagine pe telefon). "
        "Agentul de pază și/sau administratorul de cămin poate solicita suplimentar și un act de "
        "identitate valabil."
    )

    add(
        "Am acces la cămin la orice oră?",
        "Da, studenții legitimați în căminul unde sunt cazați au dreptul să intre sau să iasă din "
        "cămin la orice oră din zi/noapte."
    )

    add(
        "Pot veni vizitatori la cămin?",
        "Este interzis accesul altor persoane din exteriorul UTCN care forțează intrarea în campusurile "
        "studențești. Persoanele din afara universității nu au drept de acces neautorizat în cămine."
    )

    add(
        "Ce este interzis în căminele UTCN?",
        "În căminele și campusurile studențești UTCN este interzis:\n"
        "• Accesul persoanelor din exteriorul UTCN care forțează intrarea.\n"
        "• Introducerea băuturilor alcoolice și a substanțelor interzise (droguri, substanțe "
        "etnobotanice, etc.) în incinta căminelor și a campusurilor studențești.\n"
        "• Organizarea de petreceri unde se consumă alcool și/sau care tulbură liniștea "
        "celorlalți locatari ai căminelor.\n"
        "• Deținerea de arme albe sau de foc, precum și a șișurilor sau a obiectelor fabricate "
        "în scopul rănirii altor persoane."
    )

    add(
        "Am voie cu alcool în cămin?",
        "Nu. Este interzisă introducerea băuturilor alcoolice în incinta căminelor și a campusurilor "
        "studențești UTCN. De asemenea, este interzisă organizarea de petreceri unde se consumă alcool "
        "și/sau care tulbură liniștea celorlalți locatari ai căminelor."
    )

    add(
        "Am voie să fac petreceri în cămin?",
        "Este interzisă organizarea de petreceri unde se consumă alcool și/sau care tulbură liniștea "
        "celorlalți locatari ai căminelor UTCN."
    )

    responsabili = [
        ("Arhitectură și Urbanism", "Ș.l.dr.arh. Mihai Racu"),
        ("Automatică și Calculatoare", "Conf.dr.mat. Daniela-Ioana Inoan"),
        ("Autovehicule Rutiere, Mecatronică și Mecanică", "Prof.dr.ing. Olimpiu Mihai Tătar"),
        ("Construcții", "Ș.l.dr.ing. Ștefan-Marius Buru"),
        ("Electronică, Telecomunicații și Tehnologia Informației", "Conf.dr.ing. Emil Raul Măluțan"),
        ("Ingineria Materialelor și a Mediului", "Conf.dr.ing. Horațiu Vermeșan"),
        ("Inginerie a Instalațiilor", "Ș.l.dr.ing. Constantin Cilibiu"),
        ("Inginerie Electrică", "Conf.dr.ing. Florin Jurcă"),
        ("Inginerie Industrială, Robotică și Managementul Producției", "Conf.dr.ing. Sever Adrian Radu"),
        ("Inginerie (Baia Mare)", "Ș.l.dr.ing. Nicolae Medan"),
        ("Litere (Baia Mare)", "Ș.l.dr. Ioan Claudiu Fărcaș"),
        ("Științe (Baia Mare)", "Conf.univ.dr. Rita Monica Toader"),
    ]

    all_resp = "\n".join(f"• Facultatea de {fac}: {pers}" for fac, pers in responsabili)
    add(
        "Cine este responsabil de cazare la UTCN pe facultăți?",
        "Persoanele responsabile cu atribuții de supervizare și decizie în procesul de cazare "
        "în perioada 23-29 septembrie 2025, pe facultăți, sunt:\n" + all_resp + "\n\n"
        "Coordonare și supervizare pe toată durata anului universitar 2025-2026: "
        "Direcția Generală Administrativă — Director Ec. Cornel Mureșan."
    )

    for fac, pers in responsabili:
        add(
            f"Cine este responsabil de cazare la Facultatea de {fac}?",
            f"Persoana responsabilă cu atribuții de supervizare și decizie în procesul de cazare "
            f"la Facultatea de {fac}, în perioada 23.09.2025 – 29.09.2025, este {pers} (prodecan)."
        )

    add(
        "Cine coordonează cazarea pe tot anul universitar?",
        "Coordonarea, supervizarea și decizia pe toată durata anului universitar 2025-2026 "
        "revine Direcției Generale Administrative, condusă de Director Ec. Cornel Mureșan."
    )

    add(
        "Unde găsesc informații oficiale despre cazare la UTCN?",
        "Informații oficiale despre cazare la UTCN se găsesc la:\n"
        "• Platformă de interacțiune cu infrastructura UTCN: https://me.utcluj.app/\n"
        "• Procedura Operațională privind cazarea/decazarea: disponibilă pe site-ul UTCN.\n"
        "• Regulament taxe 2025-2026: disponibil pe site-ul UTCN.\n"
        "• Adresa UTCN: str. Memorandumului nr. 28, 400114 Cluj-Napoca, România.\n"
        "• Telefon: +40-264-401200, fax: +40-264-592055.\n"
        "• Secretariat: tel. +40-264-202209, fax +40-264-202280."
    )

    add(
        "Care este adresa UTCN?",
        "Adresa Universității Tehnice din Cluj-Napoca este: str. Memorandumului nr. 28, 400114 "
        "Cluj-Napoca, România. Telefon: +40-264-401200, fax: +40-264-592055. "
        "Secretariat: tel. +40-264-202209, fax +40-264-202280. Website: www.utcluj.ro"
    )

    add(
        "Angajații UTCN au parcare la cămin?",
        "Membrii comisiilor de cazare și angajații UTCN din campusuri de muncă, inclusiv cu "
        "autoturismele personale, au intrare liberă în cămine și/sau locurile de muncă. "
        "Aceștia beneficiază de locuri de parcare dacă au un contract de închiriere a unui "
        "loc de parcare."
    )

    add(
        "Cum funcționează cazarea la UTCN?",
        "Cazarea la UTCN se face în perioada 23-26 septembrie 2025. Studenții sunt repartizați "
        "în cămine pe baza listelor întocmite de decanatele facultăților. La prezentare, trebuie "
        "să ai actul de identitate/pașaport și avizul epidemiologic. Procesul include verificarea "
        "listelor, încărcarea selfie-ului pe me.utcluj.app, semnarea contractului pe infra.utcluj.app, "
        "plata regiei (plus 100 lei sumă nereturnabilă), primirea legitimației digitale de cămin "
        "și preluarea camerei pe bază de proces-verbal."
    )

    add(
        "Care sunt regulile de cazare la UTCN?",
        "Regulile principale de cazare la UTCN:\n"
        "• Cazarea se face personal, cu act de identitate, sau prin procură notarială.\n"
        "• Trebuie să te prezinți la data și ora programată sau să anunți comisia.\n"
        "• Este necesar aviz epidemiologic.\n"
        "• Regia primei luni + 100 lei sumă nereturnabilă se achită la cazare.\n"
        "• Selfie pe me.utcluj.app și contract pe infra.utcluj.app.\n"
        "• Este interzis accesul cu alcool, droguri sau arme în cămine.\n"
        "• Legitimația de cămin este obligatorie pentru acces pe tot parcursul anului."
    )

    add(
        "Ce trebuie să știu despre cazarea la UTCN?",
        "Informații esențiale despre cazarea la UTCN pentru anul universitar 2025-2026:\n"
        "• Perioada de cazare: 23-26 septembrie 2025.\n"
        "• Anul I licență se cazează pe 23.09, restul pe 24.09.\n"
        "• Documente: act de identitate + aviz epidemiologic.\n"
        "• Platforme: me.utcluj.app (selfie + legitimație), infra.utcluj.app (contract).\n"
        "• Costuri: regie prima lună + 100 lei taxă nereturnabilă.\n"
        "• Studenți internaționali/Erasmus: Căminul 1 sau 2 Mărăști.\n"
        "• Acces: legitimație de cămin, oricând zi/noapte.\n"
        "• Interdicții: alcool, droguri, petreceri zgomotoase, arme."
    )

    add(
        "Există cămine pentru studenți la UTCN?",
        "Da, UTCN oferă cazare în cămine studențești în mai multe campusuri: "
        "campusul Observator din Cluj-Napoca, campusul Mărăști din Cluj-Napoca, și "
        "campusurile din Baia Mare (str. Victoriei nr. 76 și str. Dr. Victor Babeș nr. 62A). "
        "Cazarea se face anual în luna septembrie, pe baza listelor de la decanate."
    )

    add(
        "Ce campusuri studențești are UTCN?",
        "UTCN are următoarele campusuri studențești cu cămine:\n"
        "• Campusul Observator — Cluj-Napoca (str. Observatorului nr. 36).\n"
        "• Campusul Mărăști — Cluj-Napoca (include Căminul 1 și Căminul 2 Mărăști).\n"
        "• Campusul Baia Mare — str. Victoriei, nr. 76.\n"
        "• Campusul Baia Mare — str. Dr. Victor Babeș, nr. 62A."
    )

    add(
        "Unde pot parca mașina la cămin?",
        "Posibilități de parcare la căminele UTCN:\n"
        "• Campusul Observator (Cluj-Napoca): se permite accesul auto în parcarea de pe str. "
        "Observatorului nr. 36, doar pentru descărcarea bagajelor, cu retragere obligatorie.\n"
        "• Campusul Mărăști (Cluj-Napoca): NU există posibilități de parcare.\n"
        "• Campusurile Baia Mare (str. Victoriei 76 și Dr. Victor Babeș 62A): acces auto "
        "în limita disponibilității locurilor de parcare."
    )

    add(
        "Unde pot găsi Procedura Operațională de cazare/decazare la UTCN?",
        "Procedura Operațională privind cazarea în/din căminele studențești UTCN poate fi "
        "consultată pe site-ul oficial UTCN. De asemenea, regulamentul taxelor pentru anul "
        "universitar 2025-2026 este disponibil pe site-ul UTCN."
    )

    add(
        "Ce se întâmplă după 30 septembrie cu cazarea?",
        "Începând cu data de 30.09.2025, Direcția Generală Administrativă va prelua în integralitate "
        "toate atribuțiile legate de continuarea activității de cazare, preluarea cererilor de cazare, "
        "repartizarea locurilor din cămine, etc. Până atunci (23-29.09.2025), atribuțiile revin "
        "comisiilor de cazare conduse de prodecanii facultăților."
    )

    return pairs

def main():
    pairs = build_cazare_qna()
    log(f"Built {len(pairs)} Q&A pairs for cazare.")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("DELETE FROM knowledge_base WHERE source = %s", (SOURCE,))
    deleted = cur.rowcount
    conn.commit()
    if deleted:
        log(f"Deleted {deleted} old entries for source '{SOURCE}'.")

    inserted = 0
    for i, (q, a) in enumerate(pairs):
        embed_text = q + " " + a
        try:
            emb = get_embedding(embed_text)
            cur.execute(
                "INSERT INTO knowledge_base (question, answer, source, embedding, chunk_type) "
                "VALUES (%s, %s, %s, %s, %s)",
                (q, a, SOURCE, format_vector(emb), "qna")
            )
            inserted += 1
        except Exception as e:
            log(f"  Embedding failed for pair {i+1}: {e}")
            cur.execute(
                "INSERT INTO knowledge_base (question, answer, source, chunk_type) "
                "VALUES (%s, %s, %s, %s)",
                (q, a, SOURCE, "qna")
            )
            inserted += 1

        if inserted % 10 == 0:
            conn.commit()
            log(f"  Progress: {inserted}/{len(pairs)}")

    conn.commit()
    cur.close()
    conn.close()
    log(f"Done. Inserted {inserted} Q&A entries for '{SOURCE}'.")

if __name__ == "__main__":
    main()
