"""Seed obd2.db with the dtc_codes schema and initial DTC data.

Running this script is idempotent — safe to run multiple times.

Usage:
    uv run seed.py              # writes to ./obd2.db
    uv run seed.py --db /tmp/x  # writes to /tmp/x
"""

import argparse
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "obd2.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS dtc_codes (
    code        TEXT PRIMARY KEY,
    category    TEXT NOT NULL,
    description TEXT NOT NULL,
    symptoms    TEXT NOT NULL,
    fix         TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS dtc_codes_fts USING fts5(
    code,
    category,
    description,
    symptoms,
    fix,
    content='dtc_codes',
    content_rowid='rowid'
);
"""

# Trigger to keep FTS index in sync with the main table
FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS dtc_codes_ai AFTER INSERT ON dtc_codes BEGIN
    INSERT INTO dtc_codes_fts(rowid, code, category, description, symptoms, fix)
    VALUES (new.rowid, new.code, new.category, new.description, new.symptoms, new.fix);
END;
CREATE TRIGGER IF NOT EXISTS dtc_codes_ad AFTER DELETE ON dtc_codes BEGIN
    INSERT INTO dtc_codes_fts(dtc_codes_fts, rowid, code, category, description, symptoms, fix)
    VALUES ('delete', old.rowid, old.code, old.category, old.description, old.symptoms, old.fix);
END;
CREATE TRIGGER IF NOT EXISTS dtc_codes_au AFTER UPDATE ON dtc_codes BEGIN
    INSERT INTO dtc_codes_fts(dtc_codes_fts, rowid, code, category, description, symptoms, fix)
    VALUES ('delete', old.rowid, old.code, old.category, old.description, old.symptoms, old.fix);
    INSERT INTO dtc_codes_fts(rowid, code, category, description, symptoms, fix)
    VALUES (new.rowid, new.code, new.category, new.description, new.symptoms, new.fix);
END;
"""

# (code, category, description, symptoms, fix)
DTC_DATA: list[tuple[str, str, str, str, str]] = [
    # ── Fuel & Air ─────────────────────────────────────────────────────────────
    (
        "P0100",
        "Fuel & Air",
        "Mass Air Flow (MAF) Sensor Circuit Malfunction",
        "Poor acceleration, rough idle, stalling, black smoke from exhaust",
        "Inspect MAF sensor wiring harness and connectors; clean or replace MAF sensor",
    ),
    (
        "P0101",
        "Fuel & Air",
        "Mass Air Flow (MAF) Sensor Circuit Range/Performance",
        "Hesitation during acceleration, poor fuel economy, rough idle",
        "Clean MAF sensor with MAF-safe cleaner; check for air leaks between MAF and throttle body; replace MAF sensor if fault persists",
    ),
    (
        "P0102",
        "Fuel & Air",
        "Mass Air Flow (MAF) Sensor Circuit Low Input",
        "Hard starting, stalling, black smoke, check engine light",
        "Inspect MAF wiring for short to ground; replace MAF sensor",
    ),
    (
        "P0103",
        "Fuel & Air",
        "Mass Air Flow (MAF) Sensor Circuit High Input",
        "Stalling, poor power, check engine light",
        "Inspect MAF sensor wiring for open circuit; replace MAF sensor",
    ),
    (
        "P0110",
        "Fuel & Air",
        "Intake Air Temperature (IAT) Sensor Circuit Malfunction",
        "Poor fuel economy, rough idle, difficulty starting in cold weather",
        "Inspect IAT sensor wiring; replace IAT sensor or MAF/IAT combined sensor",
    ),
    (
        "P0128",
        "Cooling",
        "Coolant Temperature Below Thermostat Regulating Temperature",
        "Heater performs poorly, temperature gauge stays low, poor fuel economy",
        "Replace the engine thermostat; inspect coolant temperature sensor",
    ),
    (
        "P0171",
        "Fuel & Air",
        "System Too Lean (Bank 1)",
        "Rough idle, hesitation, check engine light, poor fuel economy, misfires",
        "Check for vacuum leaks, inspect MAF sensor, test fuel pressure and injectors, replace oxygen sensor if faulty",
    ),
    (
        "P0172",
        "Fuel & Air",
        "System Too Rich (Bank 1)",
        "Black smoke from exhaust, poor fuel economy, rough idle, fuel smell",
        "Inspect MAF sensor for contamination, check for leaking fuel injectors, test fuel pressure regulator",
    ),
    (
        "P0173",
        "Fuel & Air",
        "Fuel Trim Malfunction (Bank 2)",
        "Poor fuel economy, rough idle, check engine light",
        "Inspect vacuum lines and intake manifold gasket on Bank 2; test MAF sensor",
    ),
    (
        "P0174",
        "Fuel & Air",
        "System Too Lean (Bank 2)",
        "Rough idle, hesitation, check engine light, poor fuel economy (Bank 2 side)",
        "Check for vacuum leaks on Bank 2 side, inspect MAF sensor, test fuel pressure",
    ),
    (
        "P0175",
        "Fuel & Air",
        "System Too Rich (Bank 2)",
        "Black smoke from exhaust (Bank 2), poor fuel economy, rough idle",
        "Inspect fuel injectors on Bank 2 for leaks; test fuel pressure; clean MAF sensor",
    ),
    (
        "P0190",
        "Fuel & Air",
        "Fuel Rail Pressure Sensor Circuit Malfunction",
        "Hard starting, stalling, poor performance, check engine light",
        "Inspect fuel rail pressure sensor wiring; test and replace sensor; check fuel pump output",
    ),
    (
        "P0191",
        "Fuel & Air",
        "Fuel Rail Pressure Sensor Circuit Range/Performance",
        "Hesitation, stalling, poor fuel economy",
        "Test fuel pump pressure; inspect fuel pressure regulator; check sensor wiring",
    ),
    # ── Ignition / Misfire ──────────────────────────────────────────────────────
    (
        "P0300",
        "Ignition",
        "Random/Multiple Cylinder Misfire Detected",
        "Rough idle, shaking, flashing check engine light, loss of power",
        "Inspect and replace spark plugs, ignition coils, or fuel injectors; check compression; inspect for vacuum leaks",
    ),
    (
        "P0301",
        "Ignition",
        "Cylinder 1 Misfire Detected",
        "Rough idle, shaking, loss of power, check engine light flashing",
        "Replace spark plug and ignition coil on cylinder 1; inspect fuel injector; check compression on cylinder 1",
    ),
    (
        "P0302",
        "Ignition",
        "Cylinder 2 Misfire Detected",
        "Rough idle, shaking, loss of power, check engine light flashing",
        "Replace spark plug and ignition coil on cylinder 2; inspect fuel injector; check compression on cylinder 2",
    ),
    (
        "P0303",
        "Ignition",
        "Cylinder 3 Misfire Detected",
        "Rough idle, shaking, loss of power, check engine light flashing",
        "Replace spark plug and ignition coil on cylinder 3; inspect fuel injector; check compression on cylinder 3",
    ),
    (
        "P0304",
        "Ignition",
        "Cylinder 4 Misfire Detected",
        "Rough idle, shaking, loss of power, check engine light flashing",
        "Replace spark plug and ignition coil on cylinder 4; inspect fuel injector; check compression on cylinder 4",
    ),
    (
        "P0305",
        "Ignition",
        "Cylinder 5 Misfire Detected",
        "Rough idle, shaking, loss of power, check engine light flashing",
        "Replace spark plug and ignition coil on cylinder 5; inspect fuel injector; check compression on cylinder 5",
    ),
    (
        "P0306",
        "Ignition",
        "Cylinder 6 Misfire Detected",
        "Rough idle, shaking, loss of power, check engine light flashing",
        "Replace spark plug and ignition coil on cylinder 6; inspect fuel injector; check compression on cylinder 6",
    ),
    (
        "P0316",
        "Ignition",
        "Misfire Detected On Startup (First 1000 Revolutions)",
        "Rough start, shaking on cold start, check engine light",
        "Inspect spark plugs and coils; check for fuel delivery issues; inspect PCV system",
    ),
    (
        "P0351",
        "Ignition",
        "Ignition Coil A Primary/Secondary Circuit Malfunction",
        "Misfire on cylinder 1, rough idle, check engine light",
        "Test and replace ignition coil A; inspect wiring harness to coil A",
    ),
    (
        "P0352",
        "Ignition",
        "Ignition Coil B Primary/Secondary Circuit Malfunction",
        "Misfire on cylinder 2, rough idle, check engine light",
        "Test and replace ignition coil B; inspect wiring harness to coil B",
    ),
    # ── Oxygen Sensors ──────────────────────────────────────────────────────────
    (
        "P0130",
        "Oxygen Sensors",
        "O2 Sensor Circuit Malfunction (Bank 1, Sensor 1)",
        "Poor fuel economy, rough running, failed emissions test",
        "Inspect upstream O2 sensor wiring on Bank 1; replace sensor",
    ),
    (
        "P0131",
        "Oxygen Sensors",
        "O2 Sensor Circuit Low Voltage (Bank 1, Sensor 1)",
        "Poor fuel economy, rough running, failed emissions test",
        "Inspect O2 sensor wiring for damage; replace upstream O2 sensor on Bank 1",
    ),
    (
        "P0132",
        "Oxygen Sensors",
        "O2 Sensor Circuit High Voltage (Bank 1, Sensor 1)",
        "Rich running condition, poor fuel economy, failed emissions test",
        "Check for stuck-rich condition (leaking injectors); replace upstream O2 sensor if wiring is intact",
    ),
    (
        "P0133",
        "Oxygen Sensors",
        "O2 Sensor Circuit Slow Response (Bank 1, Sensor 1)",
        "Poor fuel economy, failed emissions test",
        "Replace upstream O2 sensor on Bank 1; check for exhaust leaks before sensor",
    ),
    (
        "P0136",
        "Oxygen Sensors",
        "O2 Sensor Circuit Malfunction (Bank 1, Sensor 2)",
        "Check engine light, potential poor fuel economy",
        "Inspect downstream O2 sensor wiring on Bank 1; replace sensor",
    ),
    (
        "P0141",
        "Oxygen Sensors",
        "O2 Sensor Heater Circuit Malfunction (Bank 1, Sensor 2)",
        "Poor fuel economy, check engine light, failed emissions test",
        "Replace downstream (post-cat) O2 sensor on Bank 1; check fuse and wiring for sensor heater circuit",
    ),
    (
        "P0150",
        "Oxygen Sensors",
        "O2 Sensor Circuit Malfunction (Bank 2, Sensor 1)",
        "Poor fuel economy, rough running, failed emissions test (Bank 2)",
        "Inspect upstream O2 sensor wiring on Bank 2; replace sensor",
    ),
    (
        "P0161",
        "Oxygen Sensors",
        "O2 Sensor Heater Circuit Malfunction (Bank 2, Sensor 2)",
        "Check engine light, failed emissions test",
        "Replace downstream O2 sensor on Bank 2; check fuse and wiring",
    ),
    # ── Catalytic Converter ─────────────────────────────────────────────────────
    (
        "P0420",
        "Catalytic Converter",
        "Catalyst System Efficiency Below Threshold (Bank 1)",
        "Check engine light, poor fuel economy, sulfur smell from exhaust",
        "Inspect for exhaust leaks before catalytic converter; replace catalytic converter; rule out engine misfires first as they damage cats",
    ),
    (
        "P0430",
        "Catalytic Converter",
        "Catalyst System Efficiency Below Threshold (Bank 2)",
        "Check engine light, poor fuel economy, sulfur smell from exhaust (Bank 2)",
        "Inspect for exhaust leaks before catalytic converter on Bank 2; replace catalytic converter on Bank 2",
    ),
    # ── EVAP System ─────────────────────────────────────────────────────────────
    (
        "P0440",
        "EVAP",
        "Evaporative Emission Control System Malfunction",
        "Check engine light, fuel smell near vehicle, failed emissions test",
        "Inspect fuel cap for proper seal; check EVAP hoses and purge valve; test charcoal canister",
    ),
    (
        "P0441",
        "EVAP",
        "Evaporative Emission Control System Incorrect Purge Flow",
        "Check engine light, possible fuel smell",
        "Inspect and replace EVAP purge solenoid; check vacuum line to purge valve",
    ),
    (
        "P0442",
        "EVAP",
        "Evaporative Emission Control System Leak Detected (Small Leak)",
        "Check engine light, possible fuel odor",
        "Tighten or replace fuel cap; inspect EVAP hoses for cracks; use smoke test to locate leak",
    ),
    (
        "P0446",
        "EVAP",
        "Evaporative Emission Control System Vent Control Circuit Malfunction",
        "Check engine light, possible fuel smell",
        "Inspect EVAP vent valve; check wiring to vent solenoid; replace vent valve if faulty",
    ),
    (
        "P0455",
        "EVAP",
        "Evaporative Emission Control System Leak Detected (Large Leak)",
        "Strong fuel smell, check engine light",
        "Check fuel cap; inspect EVAP purge and vent valves; perform smoke test on EVAP system",
    ),
    (
        "P0456",
        "EVAP",
        "Evaporative Emission Control System Leak Detected (Very Small Leak)",
        "Check engine light, faint fuel odor",
        "Replace fuel cap first; inspect EVAP hoses and charcoal canister; use smoke machine for precise leak location",
    ),
    # ── EGR ─────────────────────────────────────────────────────────────────────
    (
        "P0401",
        "EGR",
        "Exhaust Gas Recirculation (EGR) Flow Insufficient",
        "Rough idle, pinging or knocking under load, failed emissions test",
        "Clean or replace EGR valve; inspect EGR passages for carbon buildup; check DPFE sensor",
    ),
    (
        "P0402",
        "EGR",
        "Exhaust Gas Recirculation (EGR) Flow Excessive",
        "Rough idle, stalling, black smoke, check engine light",
        "Inspect EGR valve for stuck-open condition; clean or replace EGR valve",
    ),
    (
        "P0404",
        "EGR",
        "Exhaust Gas Recirculation (EGR) Circuit Range/Performance",
        "Rough idle, hesitation, check engine light",
        "Clean EGR valve pintle; replace EGR valve position sensor or full EGR assembly",
    ),
    # ── Speed / Transmission ────────────────────────────────────────────────────
    (
        "P0500",
        "Transmission",
        "Vehicle Speed Sensor Malfunction",
        "Speedometer not working, harsh transmission shifts, ABS or traction control light on",
        "Inspect and replace vehicle speed sensor; check wiring harness and connectors",
    ),
    (
        "P0700",
        "Transmission",
        "Transmission Control System Malfunction",
        "Harsh or erratic shifting, transmission stuck in gear, check engine light",
        "Connect a scanner to read transmission-specific codes; inspect transmission fluid level and condition; diagnose TCM or solenoids as directed by secondary codes",
    ),
    (
        "P0715",
        "Transmission",
        "Input/Turbine Speed Sensor Circuit Malfunction",
        "Harsh shifting, transmission slipping, transmission warning light",
        "Replace input speed sensor; inspect transmission wiring harness",
    ),
    (
        "P0720",
        "Transmission",
        "Output Speed Sensor Circuit Malfunction",
        "Erratic shifting, speedometer issues, limp mode",
        "Inspect output speed sensor and wiring; replace sensor",
    ),
    (
        "P0730",
        "Transmission",
        "Incorrect Gear Ratio",
        "Slipping transmission, limp mode, transmission warning light",
        "Check transmission fluid condition; inspect solenoids; transmission service or rebuild may be required",
    ),
    (
        "P0740",
        "Transmission",
        "Torque Converter Clutch Circuit Malfunction",
        "Poor fuel economy, shuddering at highway speed, overheating transmission",
        "Inspect TCC solenoid and wiring; check transmission fluid; replace torque converter if solenoid is OK",
    ),
    (
        "P0750",
        "Transmission",
        "Shift Solenoid A Malfunction",
        "Harsh or incorrect shifting, limp mode, check engine light",
        "Replace shift solenoid A; check transmission fluid condition and level",
    ),
    # ── Battery / Charging ──────────────────────────────────────────────────────
    (
        "P0560",
        "Electrical",
        "System Voltage Malfunction",
        "Dimming lights, erratic electrical behavior, check engine light",
        "Test battery and alternator; inspect for loose ground connections",
    ),
    (
        "P0562",
        "Electrical",
        "System Voltage Low",
        "Dimming lights, slow cranking, electrical accessories malfunctioning",
        "Test and replace battery if weak; inspect alternator output; check for excessive parasitic drain",
    ),
    (
        "P0563",
        "Electrical",
        "System Voltage High",
        "Battery overcharging, warning lights, possible damage to electrical components",
        "Test alternator voltage output; replace voltage regulator or alternator if overcharging",
    ),
    (
        "P0600",
        "Electrical",
        "Serial Communication Link Malfunction",
        "Multiple warning lights, erratic gauge readings, modules not responding",
        "Inspect CAN bus wiring for damage; check ECU and module grounds; scan for module-specific DTCs",
    ),
    (
        "P0606",
        "Electrical",
        "Control Module Processor Fault (ECM/PCM)",
        "Check engine light, drivability issues, possible no-start",
        "Check ECU grounds and power supply; update or replace ECU/PCM if internal fault confirmed",
    ),
    # ── Throttle / Pedal ────────────────────────────────────────────────────────
    (
        "P0120",
        "Throttle",
        "Throttle/Pedal Position Sensor/Switch 'A' Circuit Malfunction",
        "Erratic acceleration, limp mode, stalling, rough idle",
        "Inspect TPS wiring and connectors; calibrate or replace throttle position sensor",
    ),
    (
        "P0121",
        "Throttle",
        "Throttle/Pedal Position Sensor/Switch 'A' Circuit Range/Performance",
        "Hesitation, limp mode, erratic throttle response",
        "Inspect throttle body for carbon buildup; replace TPS sensor; check for binding throttle cable",
    ),
    (
        "P0122",
        "Throttle",
        "Throttle/Pedal Position Sensor/Switch 'A' Circuit Low Input",
        "Limp mode, very poor acceleration, check engine light",
        "Inspect TPS wiring for short to ground; replace TPS sensor",
    ),
    (
        "P0123",
        "Throttle",
        "Throttle/Pedal Position Sensor/Switch 'A' Circuit High Input",
        "Limp mode, poor acceleration, check engine light",
        "Inspect TPS wiring for open circuit; replace TPS sensor",
    ),
    (
        "P0505",
        "Throttle",
        "Idle Control System Malfunction",
        "Erratic or high idle, stalling at idle",
        "Clean or replace idle air control (IAC) valve; check for vacuum leaks; inspect throttle body",
    ),
    (
        "P0507",
        "Throttle",
        "Idle Control System RPM High",
        "Engine idling too high (above 200 RPM over target)",
        "Inspect for vacuum leaks; clean throttle body; check IAC valve or electronic throttle control",
    ),
    # ── Cooling ─────────────────────────────────────────────────────────────────
    (
        "P0115",
        "Cooling",
        "Engine Coolant Temperature Sensor 1 Circuit Malfunction",
        "Engine overheating warning, poor fuel economy, hard starting when cold",
        "Inspect coolant temperature sensor wiring; replace coolant temperature sensor",
    ),
    (
        "P0116",
        "Cooling",
        "Engine Coolant Temperature Sensor 1 Circuit Range/Performance",
        "Poor fuel economy, inaccurate temperature gauge, rough cold start",
        "Inspect coolant temperature sensor; check cooling system for air pockets; replace sensor",
    ),
    (
        "P0217",
        "Cooling",
        "Engine Over Temperature Condition",
        "Temperature gauge in red zone, steam from engine bay, coolant warning light",
        "Stop vehicle immediately; check coolant level; inspect for coolant leaks, faulty thermostat, or failed water pump",
    ),
    (
        "P0218",
        "Cooling",
        "Transmission Fluid Over Temperature Condition",
        "Transmission warning light, overheating smell, limp mode",
        "Check transmission fluid level and condition; inspect transmission cooler lines; add external cooler if towing",
    ),
    # ── Oil / Pressure ──────────────────────────────────────────────────────────
    (
        "P0520",
        "Oil",
        "Engine Oil Pressure Sensor/Switch Circuit Malfunction",
        "Oil pressure warning light, suspected low oil pressure reading",
        "Check engine oil level; inspect oil pressure sensor and wiring; replace sensor; if oil pressure is genuinely low, diagnose oil pump",
    ),
    (
        "P0521",
        "Oil",
        "Engine Oil Pressure Sensor/Switch Range/Performance",
        "Fluctuating oil pressure gauge, oil pressure warning",
        "Check oil level and viscosity; inspect oil pressure sensor; test actual oil pressure mechanically",
    ),
    (
        "P0522",
        "Oil",
        "Engine Oil Pressure Sensor/Switch Low Voltage",
        "Oil pressure warning light on, check engine light",
        "Inspect sensor wiring for short to ground; replace oil pressure sensor",
    ),
    # ── ABS / Brakes ────────────────────────────────────────────────────────────
    (
        "C0031",
        "ABS & Brakes",
        "Right Front Wheel Speed Sensor Circuit Malfunction",
        "ABS warning light, traction control light, ABS not functioning",
        "Inspect right front wheel speed sensor and wiring; replace sensor; check reluctor ring for damage",
    ),
    (
        "C0034",
        "ABS & Brakes",
        "Right Rear Wheel Speed Sensor Circuit Malfunction",
        "ABS warning light, traction control light, ABS not functioning",
        "Inspect right rear wheel speed sensor and wiring; replace sensor; check reluctor ring for damage",
    ),
    (
        "C0035",
        "ABS & Brakes",
        "Left Front Wheel Speed Sensor Circuit Malfunction",
        "ABS warning light, traction control light, ABS not functioning",
        "Inspect left front wheel speed sensor and wiring; replace sensor; check reluctor ring",
    ),
    (
        "C0040",
        "ABS & Brakes",
        "Right Front Wheel Speed Sensor Signal Fault",
        "ABS warning light, erratic speedometer",
        "Inspect wheel speed sensor mounting and gap; check for metallic debris on reluctor ring",
    ),
    (
        "C0265",
        "ABS & Brakes",
        "ABS Actuator Relay Circuit Open",
        "ABS and stability control warning lights, ABS disabled",
        "Inspect ABS relay and fuse; check wiring to ABS module; replace relay or ABS module",
    ),
]


def seed(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        # Apply schema statements one by one
        for statement in SCHEMA.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(stmt)
        # Triggers contain semicolons inside BEGIN...END so use executescript
        conn.executescript(FTS_TRIGGERS)
        conn.executemany(
            "INSERT OR REPLACE INTO dtc_codes (code, category, description, symptoms, fix) VALUES (?, ?, ?, ?, ?)",
            DTC_DATA,
        )
        # Rebuild FTS to sync all rows (triggers fire per row already, but rebuild is a safety net)
        conn.execute("INSERT INTO dtc_codes_fts(dtc_codes_fts) VALUES ('rebuild')")
        conn.commit()
    print(f"Seeded {len(DTC_DATA)} DTC codes into {db_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the OBD-II SQLite database.")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to the SQLite database file (default: ./obd2.db)",
    )
    args = parser.parse_args()
    seed(args.db)
