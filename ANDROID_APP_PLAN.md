# NovaFlow für Android, Umsetzungsplan

Stand: 25. Juli 2026. Version 2, nach Prüfung der ersten Fassung gegen die Android und Wispr Dokumentation.

Dieser Plan beschreibt den Weg zu einer eigenständigen Android App, die dem Grundgedanken von NovaFlow folgt, aber technisch neu aufgebaut wird. Kein eigenes Backend, kein Nutzerkonto, keine zentrale Datenbank. Jeder Nutzer bringt seinen eigenen OpenRouter Schlüssel mit, genau wie bei der Desktop Version. Damit bleibt die datenschutzrechtliche Lage einfach.

## Zielbild

Eine schwebende Blase erscheint über anderen Apps, sobald der Nutzer sie aktiviert hat. Tippen oder Halten startet die Aufnahme, die Sprache wird über OpenRouter transkribiert und veredelt, und der fertige Text landet automatisch im gerade fokussierten Textfeld, egal in welcher App. Wörterbuch, Textbausteine, Verlauf und Notizen funktionieren lokal auf dem Gerät, angelehnt an das, was `src/utils/dictionary_store.py`, `snippets_store.py`, `history_store.py` und `notes_store.py` in der Desktop Version heute schon leisten.

## Das größte offene Risiko, vor allem anderen zu klären

Ab Android 14 prüft das System beim Start eines Vordergrunddienstes vom Typ Mikrofon, ob die App gerade die Berechtigung `RECORD_AUDIO` besitzt. Diese Berechtigung gilt nur während der Nutzung, also nur solange die App im Vordergrund ist. Startet eine App aus dem Hintergrund heraus einen Mikrofon Vordergrunddienst, wirft das System eine `SecurityException`.

Genau das will die Overlay Architektur aber tun, nämlich eine Aufnahme starten, während eine fremde App im Vordergrund ist.

Es gibt einen plausiblen Auflösungsweg. Ein sichtbares Overlay Fenster kann der App den Status "im Vordergrund" verschaffen, sodass die Berechtigung greift. Wispr Flow funktioniert nachweislich, also muss es einen gangbaren Weg geben. Belegt ist er in dieser Recherche jedoch nicht, und ob er auf allen Herstellern und Android Versionen trägt, ist offen.

**Konsequenz für die Planung:** Bevor irgendetwas anderes gebaut wird, entsteht ein Wegwerf Prototyp, der ausschließlich prüft, ob aus einem sichtbaren Overlay heraus eine Audioaufnahme gestartet werden kann, auf einem echten Gerät mit aktueller Android Version. Scheitert das, ist die gesamte Overlay Architektur hinfällig und es bleibt nur der Weg über eine eigene Tastatur. Diese Frage entscheidet über das ganze Projekt und darf nicht ans Ende geschoben werden.

## Warum die Architektur zweigeteilt ist

Die Haupt App, also Einstellungen, Wörterbuch, Textbausteine, Verlauf und Notizen, wird in Flutter gebaut.

Für das Overlay selbst gibt es fertige Flutter Pakete wie `flutter_overlay_window`. Damit kann auch der Inhalt der schwebenden Blase in Dart geschrieben werden, der native Unterbau steckt im Paket. Die erste Fassung dieses Plans hat das zu streng dargestellt.

Nativer Kotlin Code bleibt trotzdem nötig, und zwar für den Bedienungshilfen Dienst, der den Text in fremde Apps einsetzt. Dafür gibt es keinen Flutter Ersatz. Angebunden wird er über einen MethodChannel.

## Die beiden entscheidenden Berechtigungen

**Anzeige über anderen Apps**, technisch `SYSTEM_ALERT_WINDOW`. Erlaubt das Zeichnen der schwebenden Blase. Der Nutzer muss sie manuell in den Systemeinstellungen freigeben.

**Bedienungshilfen Dienst**, technisch ein `AccessibilityService`. Ohne ihn erscheint der Text nicht automatisch. Seit Android 10 dürfen Apps im Hintergrund nicht mehr auf die Zwischenablage zugreifen, ausgenommen sind nur die App mit Fokus und die aktive Tastatur. Wispr Flow bestätigt in der eigenen Dokumentation, dass genau dieser Dienst benötigt wird, um diktierten Text in fremde Apps einzusetzen, und dass er beim Einrichten zusätzlich zur Overlay Berechtigung freigeschaltet werden muss.

Hinzu kommt ab Android 14 die verpflichtende Angabe eines Vordergrunddienst Typs im Manifest, samt passender Berechtigung. Das ist eine eigene, gesondert zu begründende Sache gegenüber Google Play.

## Phasenplan

**Phase 0, Machbarkeitsprüfung.** Der oben beschriebene Wegwerf Prototyp zum Mikrofonzugriff aus dem Overlay. Nichts anderes. Ergebnis ist eine belastbare Ja oder Nein Antwort zur Architektur.

**Phase 1, Werkzeuge und Grundgerüst.** Flutter SDK und Android Studio einrichten, `flutter doctor` sauber durchlaufen lassen, leeres Projekt auf einem echten Gerät starten.

**Phase 2, Haupt App ohne Overlay.** Einstellungen für den OpenRouter Schlüssel, Auswahl des Sprachmodells, Wörterbuch, Textbausteine, Verlauf, Notizen. Alles lokal gespeichert. Dazu die vollständige Sprachlogik innerhalb der App, also Aufnahme, Versand an OpenRouter, Veredelung, Anzeige des Ergebnisses. Am Ende dieser Phase existiert eine nutzbare, wenn auch unauffällige Diktier App.

**Phase 3, Overlay.** Die schwebende Blase über `flutter_overlay_window`, Bedienung per Tippen und Halten, Auslösen der Aufnahme aus dem Overlay heraus.

**Phase 4, Texteinfügung.** Der native Bedienungshilfen Dienst in Kotlin, der das fokussierte Textfeld erkennt und den fertigen Text einsetzt. Technisch der anspruchsvollste Teil.

**Phase 5, Zusammenführung.** Overlay und Haupt App teilen dieselben lokalen Daten, Wörterbuch und Textbausteine wirken also auch beim Diktat über die Blase.

**Phase 6, Geräte Tests.** Mehrere Hersteller, nicht nur Emulator oder Pixel. Xiaomi, Samsung und Huawei schränken Hintergrunddienste und Overlays über eigene Akku Optimierungen zusätzlich ein. Das ist bei Overlay Apps die häufigste Fehlerquelle im Feld.

**Phase 7, Play Store Vorbereitung.** Entwicklerkonto, Datenschutzerklärung, Begründung für den Bedienungshilfen Dienst, Begründung für den Vordergrunddienst Typ, Abschnitt zur Datensicherheit.

**Phase 8, interner Test, dann schrittweise Veröffentlichung.**

## Zwei getrennte Google Play Hürden

**Bedienungshilfen Dienst.** Google prüft solche Apps strenger, weil dieselbe Technik von Schadsoftware missbraucht wird. Die Begründung im Formular muss zur tatsächlichen Funktion passen. Google Play fragt zudem beim Nutzer in Abständen nach, ob die Berechtigung bestehen bleiben soll. Das ist normales Systemverhalten und keine Fehlfunktion, verunsichert Nutzer aber regelmäßig und sollte in der eigenen Hilfe erklärt werden.

**Vordergrunddienst Typ.** Seit Android 14 ist die Deklaration verpflichtend und bei Google Play gesondert zu begründen.

Zwei unabhängige Prüfungen, beide mit Rückfragerisiko. Beide brauchen Zeit und können zu Nachbesserungen führen. Da sich die Regeln ändern, ist ein aktueller Blick in die Play Console zum Zeitpunkt der Einreichung Pflicht.

## Zum Datenschutz, eine Einschränkung gegenüber der ersten Fassung

Der Verzicht auf ein eigenes Backend bleibt richtig und ist der wesentliche Vereinfacher. Die Aussage "es werden keine Daten erhoben" ist so aber nicht ganz haltbar. Ein Bedienungshilfen Dienst kann grundsätzlich Inhalte fremder Apps auslesen. Selbst wenn die App das nur zweckgebunden für das Einsetzen von Text nutzt, ist das erklärungsbedürftig, gegenüber Google Play wie gegenüber den Nutzern. Die Datenschutzerklärung sollte deshalb ausdrücklich benennen, worauf der Dienst zugreift, was damit geschieht, und dass nichts davon das Gerät verlässt.

Unverändert gilt: Audiodaten gehen an OpenRouter, mit dem Schlüssel des Nutzers. Das gehört ebenfalls klar in die Erklärung.

## Was bewusst nicht in der ersten Version steckt

Lokale Spracherkennung über Whisper fällt vorerst weg, `faster-whisper` läuft nicht auf Android. Eine spätere Ergänzung über `whisper.cpp` ist denkbar, aber ein eigenes Teilprojekt.

Ein Konto oder eine Synchronisation zwischen Desktop und Handy ist nicht Teil dieses Plans. Falls später gewünscht, wäre Export und Import als Datei der naheliegende Zwischenschritt ohne eigenes Backend.

## Zur iOS Frage, wichtig für die Erwartungshaltung

Diese Architektur lässt sich **nicht** auf iOS übertragen. Apple erlaubt Drittanbietern weder Overlays über fremden Apps noch etwas, das dem Bedienungshilfen Dienst entspricht. Auf iOS bleibt nur die Tastatur Erweiterung.

Wispr Flow zeigt, wie umständlich das dort ist. Die Tastatur Erweiterung darf selbst nicht dauerhaft auf das Mikrofon zugreifen, deshalb schickt Wispr den Nutzer beim Start kurz in die Haupt App, aktiviert dort eine zeitlich begrenzte Sitzung und springt zurück. Die Sitzung läuft je nach Einstellung nach 5 Minuten, 15 Minuten oder einer Stunde ab.

Für dich heißt das: Der schwierige Teil, also das Einfügen von Text in fremde Apps, ist auf beiden Plattformen grundverschieden und wird zweimal gebaut. Flutter spart die gemeinsame Oberfläche, Einstellungen, Wörterbuch, Textbausteine, Verlauf, Notizen und die OpenRouter Anbindung. Das ist ein echter Gewinn, aber es ist nicht die "eine Codebasis für beides", nach der es zu Beginn klang. Diese Erwartung sollte man von vornherein korrigieren.

## Technologie Zusammenfassung

Flutter mit Dart für die Haupt App, Riverpod zur Zustandsverwaltung, Dio für die Anfragen an OpenRouter, `flutter_secure_storage` für den API Schlüssel, `flutter_overlay_window` für die Blase. Ein natives Kotlin Modul für den Bedienungshilfen Dienst, angebunden über MethodChannel. Lokale Datenhaltung über `sqflite` oder `drift`, beide aktiv gepflegt. Kein Server, keine Datenbank außerhalb des Geräts.

Die Mindest Android Version sollte bewusst gesetzt werden. Wispr Flow verlangt Android 13, was einen Hinweis darauf gibt, wie viel Aufwand ältere Versionen bei Overlays und Diensten verursachen. Ein hoher Mindestwert kostet Reichweite, spart aber viel Sonderbehandlung.

## Grobe Einordnung des Aufwands

Phase 0 ist klein, aber entscheidend. Phase 1 und 2 sind mit Flutter Grundwissen in überschaubarer Zeit machbar. Phase 3 und 4 sind der eigentlich schwierige Teil und hängen stark davon ab, wie vertraut natives Android ist, hier ist mit deutlich mehr Zeit zu rechnen als für alles davor. Phase 6 und 7 ziehen sich erfahrungsgemäß, weil Geräte Eigenheiten und die Prüfung durch Google nur bedingt in der eigenen Hand liegen.

## Sinnvoller nächster Schritt

Phase 0. Erst wenn feststeht, dass die Aufnahme aus dem Overlay heraus auf einem echten Gerät funktioniert, lohnt sich Aufwand in Phase 1 und 2.

## Quellen

- Android Developers, Foreground service types are required: https://developer.android.com/about/versions/14/changes/fgs-types-required
- Android Developers, Restrictions on starting a foreground service from the background: https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start
- Android Developers, Privacy changes in Android 10, Zwischenablage: https://developer.android.com/about/versions/10/privacy/changes
- Wispr Flow, Accessibility Permission on Android: https://docs.wisprflow.ai/articles/7669452251-accessibility-permission-on-android
- Wispr Flow, Set up the Flow keyboard on iPhone: https://docs.wisprflow.ai/articles/7453988911-set-up-the-flow-keyboard-on-iphone
- flutter_overlay_window: https://pub.dev/packages/flutter_overlay_window
