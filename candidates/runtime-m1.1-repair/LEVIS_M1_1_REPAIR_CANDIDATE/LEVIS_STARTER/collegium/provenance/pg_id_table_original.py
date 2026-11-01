"""
levis/collegium/pg_id_table.py

Canonical PG identifier lookup table.

Maps item_key → Project Gutenberg catalogue ID string.

Rules:
  - Table MUST be total over all 191 PG-sourced items in the registry.
  - Known PG catalogue IDs are stored as numeric strings (e.g. '1228').
  - Items with no confirmed PG catalogue number are stored as '' (empty string).
  - Non-PG items are NOT in this table; export.py applies '' for them directly.
  - No omissions. Absence of a PG item_key from the table is a Phase 1 contract
    violation; tests enforce total coverage.

Authority: LEVIS_PG_FETCHER_CONTRACT_v0_1 §2.4 and §3.1.
Source:    Collegium build documents Parts 1–5 (session transcripts).
           Supplemented by PG catalogue lookup for items where the build
           documents cited PG as source but did not record a number.

Update policy:
  Corrections or newly-resolved IDs must be applied here, followed by a
  fresh export pass (export.py → collegium_registry_v1_0.json) and a
  version bump in the promotion memo.
"""

PG_ID_TABLE: dict[str, str] = {

    # ── Category 1 — Logic ────────────────────────────────────────────────────
    "1:1":   "",       # Aristotle — Prior Analytics
    "1:2":   "",       # Aristotle — Posterior Analytics
    "1:3":   "",       # Aristotle — Topics
    "1:8":   "",       # Francis Bacon — Novum Organum
    "1:10":  "36884",  # George Boole — Mathematical Analysis of Logic
    "1:11":  "",       # John Stuart Mill — A System of Logic
    "1:12":  "15114",  # George Boole — Laws of Thought
    "1:14":  "28696",  # Lewis Carroll — Symbolic Logic, Part I
    "1:16":  "",       # Aristotle — Categories
    "1:19":  "41588",  # Bertrand Russell — Introduction to Mathematical Philosophy
    "1:20":  "5740",   # Ludwig Wittgenstein — Tractatus Logico-Philosophicus
    "1:R1":  "",       # Aristotle — Categories (alt. slot)
    "1:R3":  "36884",  # George Boole — Mathematical Analysis of Logic (alt. slot)

    # ── Category 2 — Mathematics ──────────────────────────────────────────────
    "2:19":  "17384",  # David Hilbert — The Foundations of Geometry
    "2:20":  "",       # Henri Poincaré — Science and Hypothesis

    # ── Category 3 — Ethics ───────────────────────────────────────────────────
    "3:1":   "1497",   # Plato — Republic
    "3:2":   "1658",   # Plato — Phaedo
    "3:3":   "",       # Aristotle — Nicomachean Ethics
    "3:7":   "",       # Epictetus — Enchiridion
    "3:8":   "2680",   # Marcus Aurelius — Meditations
    "3:9":   "",       # Thomas Aquinas — Summa Theologica Part I-II
    "3:10":  "",       # Niccolò Machiavelli — The Prince
    "3:11":  "3207",   # Thomas Hobbes — Leviathan
    "3:12":  "",       # Benedict de Spinoza — Ethics
    "3:13":  "",       # David Hume — Treatise of Human Nature, Book III
    "3:14":  "",       # David Hume — Enquiry Concerning Principles of Morals
    "3:15":  "",       # Immanuel Kant — Groundwork of the Metaphysics of Morals
    "3:16":  "",       # Immanuel Kant — Critique of Practical Reason
    "3:17":  "",       # Jeremy Bentham — Introduction to Principles of Morals and Legislation
    "3:18":  "11224",  # John Stuart Mill — Utilitarianism
    "3:20":  "",       # G.E. Moore — Principia Ethica
    "3:R1":  "",       # Plato — Philebus
    "3:R4":  "34901",  # John Stuart Mill — On Liberty

    # ── Category 4 — Political Theory ─────────────────────────────────────────
    "4:1":   "7142",   # Thucydides — History of the Peloponnesian War (cross-list: History)
    "4:2":   "1497",   # Plato — Republic (cross-list: Ethics)
    "4:3":   "",       # Aristotle — Politics
    "4:6":   "2130",   # Thomas More — Utopia
    "4:10":  "3207",   # Thomas Hobbes — Leviathan (cross-list: Ethics)
    "4:13":  "",       # Jean-Jacques Rousseau — The Social Contract
    "4:14":  "",       # Edmund Burke — Reflections on the Revolution in France
    "4:15":  "1404",   # Hamilton, Madison, Jay — The Federalist Papers
    "4:16":  "3420",   # Mary Wollstonecraft — A Vindication of the Rights of Woman
    "4:17":  "815",    # Alexis de Tocqueville — Democracy in America
    "4:18":  "",       # John Stuart Mill — Considerations on Representative Government
    "4:19":  "61",     # Karl Marx & Friedrich Engels — Manifesto of the Communist Party
    "4:20":  "4341",   # Peter Kropotkin — Mutual Aid: A Factor of Evolution
    "4:R1":  "3742",   # Thomas Paine — Rights of Man
    "4:R2":  "",       # Herbert Spencer — The Man Versus the State
    "4:R3":  "",       # Walter Bagehot — The English Constitution
    "4:R4":  "5093",   # Mikhail Bakunin — God and the State

    # ── Category 5 — History ──────────────────────────────────────────────────
    "5:1":   "2456",   # Herodotus — Histories
    "5:2":   "7142",   # Thucydides — History of the Peloponnesian War
    "5:3":   "1170",   # Xenophon — Anabasis
    "5:5":   "",       # Livy — Ab Urbe Condita
    "5:6":   "",       # Josephus — The Jewish War
    "5:7":   "674",    # Plutarch — Parallel Lives
    "5:8":   "",       # Tacitus — The Annals
    "5:9":   "",       # Tacitus — The Histories
    "5:12":  "",       # Einhard — Life of Charlemagne
    "5:14":  "",       # Edward Gibbon — Decline and Fall of the Roman Empire, Vol. I
    "5:15":  "1301",   # Thomas Carlyle — The French Revolution
    "5:18":  "5765",   # Henry Adams — The Education of Henry Adams
    "5:R3":  "3743",   # Thomas Paine — The Age of Reason
    "5:R4":  "22994",  # Frederick Jackson Turner — The Frontier in American History
    "5:R5":  "6400",   # Suetonius — The Twelve Caesars

    # ── Category 6 — Psychology ───────────────────────────────────────────────
    "6:4":   "10615",  # John Locke — An Essay Concerning Human Understanding
    "6:17":  "33994",  # Sigmund Freud — The Interpretation of Dreams

    # ── Category 7 — Education ────────────────────────────────────────────────
    "7:1":   "",       # Confucius — The Analects
    "7:2":   "",       # Plato — Meno
    "7:3":   "",       # Plato — Protagoras
    "7:4":   "",       # Plato — Phaedrus
    "7:8":   "",       # Michel de Montaigne — Essays I.26 'On the Education of Children'
    "7:10":  "",       # John Locke — Some Thoughts Concerning Education
    "7:11":  "",       # Jean-Jacques Rousseau — Émile
    "7:15":  "",       # Herbert Spencer — Education: Intellectual, Moral, and Physical
    "7:16":  "",       # Friedrich Nietzsche — Schopenhauer as Educator
    "7:18":  "",       # John Dewey — The School and Society
    "7:19":  "408",    # W.E.B. Du Bois — The Souls of Black Folk
    "7:20":  "852",    # John Dewey — Democracy and Education
    "7:R2":  "2376",   # Booker T. Washington — Up from Slavery
    "7:R3":  "29635",  # Maria Montessori — The Montessori Method
    "7:R4":  "",       # William James — Talks to Teachers on Psychology

    # ── Category 8 — Natural Philosophy ──────────────────────────────────────
    "8:1":   "",       # Plato — Timaeus
    "8:7":   "",       # Galileo Galilei — Dialogues Concerning Two New Sciences
    "8:9":   "",       # Robert Boyle — The Sceptical Chymist
    "8:11":  "33504",  # Isaac Newton — Opticks
    "8:17":  "",       # James Clerk Maxwell — Matter and Motion
    "8:R3":  "",       # Francis Bacon — Novum Organum (alt. slot for cat 8)

    # ── Category 9 — Economics ────────────────────────────────────────────────
    "9:1":   "",       # Xenophon — Oeconomicus
    "9:7":   "",       # Adam Smith — The Wealth of Nations
    "9:8":   "",       # Thomas Robert Malthus — An Essay on the Principle of Population
    "9:9":   "",       # David Ricardo — On the Principles of Political Economy and Taxation
    "9:10":  "",       # John Stuart Mill — Principles of Political Economy
    "9:12":  "",       # Henry George — Progress and Poverty
    "9:14":  "833",    # Thorstein Veblen — The Theory of the Leisure Class

    # ── Category 10 — Rhetoric & Poetics ─────────────────────────────────────
    "10:1":  "",       # Plato — Gorgias
    "10:2":  "",       # Aristotle — Rhetoric
    "10:3":  "",       # Aristotle — Poetics
    "10:9":  "",       # John Dryden — An Essay of Dramatic Poesy
    "10:10": "",       # Alexander Pope — An Essay on Criticism
    "10:11": "",       # Edmund Burke — A Philosophical Enquiry…Sublime and Beautiful
    "10:15": "",       # Samuel Taylor Coleridge — Biographia Literaria
    "10:16": "",       # Percy Bysshe Shelley — A Defence of Poetry
    "10:17": "",       # Matthew Arnold — Essays in Criticism, First Series
    "10:18": "",       # Oscar Wilde — Intentions
    "10:19": "",       # Leo Tolstoy — What Is Art?
    "10:R1": "",       # Plato — Ion
    "10:R3": "",       # Ben Jonson — Timber, or Discoveries
    "10:R4": "",       # Walter Pater — Appreciations: With an Essay on Style

    # ── Category 11 — Aesthetics ──────────────────────────────────────────────
    "11:1":  "",       # Plato — Symposium
    "11:2":  "",       # Plato — Phaedrus
    "11:3":  "",       # Aristotle — Poetics
    "11:4":  "",       # Vitruvius — De Architectura
    "11:6":  "",       # Edmund Burke — A Philosophical Enquiry…Sublime and Beautiful
    "11:7":  "",       # Immanuel Kant — Critique of Judgment
    "11:9":  "",       # Arthur Schopenhauer — The World as Will and Representation, Vol. I
    "11:12": "",       # John Ruskin — The Stones of Venice, Vol. II: 'The Nature of Gothic'
    "11:13": "",       # Walter Pater — The Renaissance: Studies in Art and Poetry
    "11:14": "",       # Leo Tolstoy — What Is Art?

    # ── Category 12 — Theology & Religion ────────────────────────────────────
    "12:1":  "2388",   # Bhagavad Gītā
    "12:2":  "",       # Dhammapada
    "12:4":  "1658",   # Plato — Phaedo (cross-list: Ethics)
    "12:5":  "2680",   # Marcus Aurelius — Meditations (cross-list: Ethics)
    "12:6":  "",       # Augustine of Hippo — The City of God
    "12:8":  "",       # Maimonides — Guide for the Perplexed
    "12:9":  "1653",   # Thomas à Kempis — The Imitation of Christ
    "12:11": "",       # Martin Luther — On the Freedom of a Christian
    "12:12": "",       # John Calvin — Institutes of the Christian Religion
    "12:13": "",       # Baruch Spinoza — Theologico-Political Treatise
    "12:14": "",       # Blaise Pascal — Pensées
    "12:15": "131",    # John Bunyan — The Pilgrim's Progress
    "12:17": "621",    # William James — The Varieties of Religious Experience
    "12:18": "",       # Julian of Norwich — Revelations of Divine Love

    # ── Category 13 — Sociology & Anthropology ───────────────────────────────
    "13:1":  "2456",   # Herodotus — Histories (ethnographic sections) (same as 5:1)
    "13:4":  "",       # Henry Sumner Maine — Ancient Law
    "13:5":  "",       # Herbert Spencer — The Study of Sociology
    "13:9":  "833",    # Thorstein Veblen — The Theory of the Leisure Class (same as 9:14)
    "13:12": "310",    # Charlotte Perkins Gilman — Women and Economics
    "13:R3": "408",    # W.E.B. Du Bois — The Souls of Black Folk (same as 7:19)
    "13:R4": "3420",   # Mary Wollstonecraft — A Vindication of the Rights of Woman (same as 4:16)

    # ── Category 14 — Medicine & Biology ─────────────────────────────────────
    "14:7":  "1228",   # Charles Darwin — On the Origin of Species
    "14:8":  "",       # Charles Darwin — The Descent of Man
    "14:9":  "",       # Charles Darwin — The Expression of the Emotions in Man and Animals
    "14:10": "",       # Thomas Henry Huxley — Man's Place in Nature
    "14:17": "",       # Francis Galton — Hereditary Genius

    # ── Category 15 — Law & Jurisprudence ────────────────────────────────────
    "15:1":  "",       # Hammurabi — Code of Hammurabi
    "15:2":  "",       # Plato — Laws (Nomoi)
    "15:9":  "",       # William Blackstone — Commentaries on the Laws of England
    "15:10": "",       # Jeremy Bentham — Introduction to Principles of Morals and Legislation
    "15:12": "",       # Henry Sumner Maine — Ancient Law
    "15:14": "2449",   # Oliver Wendell Holmes Jr. — The Common Law
    "15:R1": "",       # Thomas Aquinas — Summa Theologica Part II-II (on justice)
    "15:R3": "",       # John Stuart Mill — The Subjection of Women
    "15:R4": "",       # Aristotle — Nicomachean Ethics Book V (on justice)

    # ── Category 16 — Literature & Literary Theory ───────────────────────────
    "16:1":  "2199",   # Homer — Iliad
    "16:2":  "1727",   # Homer — Odyssey
    "16:3":  "228",    # Virgil — Aeneid
    "16:4":  "8800",   # Dante Alighieri — The Divine Comedy
    "16:5":  "2383",   # Geoffrey Chaucer — The Canterbury Tales
    "16:6":  "996",    # Miguel de Cervantes — Don Quixote
    "16:7":  "1787",   # William Shakespeare — Hamlet
    "16:8":  "1128",   # William Shakespeare — King Lear
    "16:9":  "26",     # John Milton — Paradise Lost
    "16:10": "",       # Goethe — Faust, Part I
    "16:11": "",       # William Wordsworth — Preface to Lyrical Ballads
    "16:12": "",       # Samuel Taylor Coleridge — Biographia Literaria
    "16:13": "",       # Percy Bysshe Shelley — A Defence of Poetry
    "16:14": "",       # Matthew Arnold — Essays in Criticism, First Series
    "16:16": "",       # Oscar Wilde — Intentions
    "16:17": "",       # Leo Tolstoy — What Is Art?
    "16:20": "",       # Walter Pater — Appreciations: With an Essay on Style
    "16:R1": "",       # Sophocles — Oedipus Rex
    "16:R4": "",       # Walter Pater — Appreciations (alt. slot)

    # ── Category 17 — Linguistics & Grammar ──────────────────────────────────
    "17:1":  "",       # Plato — Cratylus
    "17:2":  "",       # Aristotle — On Interpretation (De Interpretatione)
    "17:18": "",       # Edward Sapir — Language: An Introduction to the Study of Speech

    # ── Category 18 — Geography & Exploration ────────────────────────────────
    "18:1":  "2456",   # Herodotus — Histories (geographical sections) (same as 5:1)
    "18:5":  "1039",   # David Livingstone — Missionary Travels and Researches in South Africa
    "18:10": "944",    # Charles Darwin — Voyage of the Beagle
    "18:11": "2530",   # Alfred Russel Wallace — The Malay Archipelago
    "18:12": "895",    # John Wesley Powell — Exploration of the Colorado River of the West
    "18:R4": "1039",   # David Livingstone — Missionary Travels (alt. slot; same as 18:5)
    "18:R5": "4341",   # Peter Kropotkin — Mutual Aid (same as 4:20)

    # ── Category 19 — Music Theory ────────────────────────────────────────────
    "19:1":  "1497",   # Plato — Republic Books II–III (same as 3:1)
    "19:2":  "",       # Aristotle — Politics Book VIII (same as 4:3)

    # ── Category 20 — Architecture, Engineering & Technology ─────────────────
    "20:1":  "",       # Vitruvius — De Architectura (same as 11:4)
    "20:7":  "",       # John Ruskin — The Seven Lamps of Architecture
    "20:8":  "",       # John Ruskin — The Stones of Venice Vol. II (same as 11:12)
    "20:16": "6435",   # Frederick Winslow Taylor — The Principles of Scientific Management
    "20:18": "5765",   # Henry Adams — The Dynamo and the Virgin (same as 5:18)
    "20:R5": "",       # Ralph Waldo Emerson — 'The American Scholar' and 'Art'
}


def get_pg_id(item_key: str) -> str:
    """Return the PG catalogue ID for an item_key, or '' if not in table."""
    return PG_ID_TABLE.get(item_key, "")
