"""Build FHIR R4 resources from database rows, and validate them with the fhirclient R4 models.

Validation here means "valid against base FHIR R4 structures" (types, required elements,
no unknown fields) plus a check that every reference resolves inside the bundle.
It is NOT validation against the ABDM FHIR Implementation Guide profiles.
"""
import html

from fhirclient.models import (appointment, bundle, capabilitystatement, composition, condition, diagnosticreport,
                               encounter, medicationrequest, observation, organization, patient, practitioner)
from fhirclient.models.fhirabstractbase import FHIRValidationError

from .config import FHIR_BASE_URL
from .database import utcnow
from .loinc import LOINC_SYSTEM, UCUM_SYSTEM, get_concept

# Identifier systems issued by this application (not ABHA / ABDM systems). Replace example.org with
# your own domain before production (see docs/PRODUCTION_PLAN.md).
ID_SYSTEM = "https://abdm-connect.example.org/fhir/sid"
INTERPRETATION = {"L": "Low", "N": "Normal", "H": "High"}
FHIR_CLASSES = {
    "Patient": patient.Patient, "Organization": organization.Organization,
    "Practitioner": practitioner.Practitioner, "Observation": observation.Observation,
    "DiagnosticReport": diagnosticreport.DiagnosticReport, "Composition": composition.Composition,
    "Bundle": bundle.Bundle, "CapabilityStatement": capabilitystatement.CapabilityStatement,
    "Encounter": encounter.Encounter, "Condition": condition.Condition,
    "MedicationRequest": medicationrequest.MedicationRequest, "Appointment": appointment.Appointment,
}


def iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def ref(resource_type, id_):
    return {"reference": f"{resource_type}/{id_}"}


def patient_resource(p):
    res = {
        "resourceType": "Patient",
        "id": str(p.id),
        "identifier": [{
            "type": {"text": "Facility-issued patient identifier (not an ABHA number)"},
            "system": f"{ID_SYSTEM}/patient-id",
            "value": p.patient_code,
        }],
        "name": [{"text": p.full_name}],
        "gender": p.gender,
        "birthDate": p.birth_date.isoformat(),
    }
    if p.abha_number:
        # Verified through the local mock ABDM server only, so the system URI is ours, not ABDM's.
        res["identifier"].append({
            "type": {"text": "ABHA number (verified by mock ABDM server, not real ABDM)"},
            "system": f"{ID_SYSTEM}/mock-abha-number",
            "value": p.abha_number,
        })
    if p.phone:
        res["telecom"] = [{"system": "phone", "value": p.phone, "use": "mobile"}]
    return res


def organization_resource(f):
    return {
        "resourceType": "Organization",
        "id": str(f.id),
        "identifier": [{"system": f"{ID_SYSTEM}/facility-id", "value": f.facility_code}],
        "type": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/organization-type",
            "code": "prov", "display": "Healthcare Provider",
        }], "text": "Laboratory" if f.facility_type == "LAB" else "Hospital"}],
        "name": f.name,
        "address": [{"city": f.city, "country": "IN"}] if f.city else [],
    }


def practitioner_resource(u):
    return {
        "resourceType": "Practitioner",
        "id": str(u.id),
        "identifier": [{"system": f"{ID_SYSTEM}/staff-id", "value": u.username}],
        "name": [{"text": u.full_name}],
    }


def observation_resource(o, r):
    res = {
        "resourceType": "Observation",
        "id": str(o.id),
        "status": r.status,
        "category": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "laboratory", "display": "Laboratory",
        }]}],
        "code": {"coding": [{"system": LOINC_SYSTEM, "code": o.loinc_code, "display": o.loinc_display}],
                 "text": o.test_name},
        "subject": ref("Patient", r.patient_id),
        "effectiveDateTime": iso(r.collected_at),
        "issued": iso(r.issued_at),
        "performer": [ref("Organization", r.facility_id), ref("Practitioner", r.created_by_user_id)],
        "valueQuantity": {"value": o.value, "unit": o.unit, "system": UCUM_SYSTEM, "code": o.unit},
    }
    if o.interpretation:
        res["interpretation"] = [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
            "code": o.interpretation, "display": INTERPRETATION[o.interpretation],
        }]}]
    rng = {}
    if o.ref_low is not None:
        rng["low"] = {"value": o.ref_low, "unit": o.unit, "system": UCUM_SYSTEM, "code": o.unit}
    if o.ref_high is not None:
        rng["high"] = {"value": o.ref_high, "unit": o.unit, "system": UCUM_SYSTEM, "code": o.unit}
    if rng:
        res["referenceRange"] = [rng]
    return res


def diagnostic_report_resource(r):
    code = {"text": r.title}
    if r.panel_loinc_code:
        code["coding"] = [{"system": LOINC_SYSTEM, "code": r.panel_loinc_code, "display": get_concept(r.panel_loinc_code)["display"]}]
    res = {
        "resourceType": "DiagnosticReport",
        "id": str(r.id),
        "status": r.status,
        "category": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/v2-0074", "code": "LAB", "display": "Laboratory",
        }]}],
        "code": code,
        "subject": ref("Patient", r.patient_id),
        "effectiveDateTime": iso(r.collected_at),
        "issued": iso(r.issued_at),
        "performer": [ref("Organization", r.facility_id)],
        "resultsInterpreter": [ref("Practitioner", r.created_by_user_id)],
        "result": [ref("Observation", o.id) for o in r.observations],
    }
    if r.conclusion:
        res["conclusion"] = r.conclusion
    return res


def report_bundle(r):
    """A FHIR 'document' Bundle: Composition first, then every resource it refers to."""
    comp = {
        "resourceType": "Composition",
        "id": str(r.id),
        "status": "final",
        "type": {"coding": [{"system": LOINC_SYSTEM, "code": "11502-2", "display": "Laboratory report"}]},
        "subject": ref("Patient", r.patient_id),
        "date": iso(r.issued_at),
        "author": [ref("Organization", r.facility_id)],
        "title": r.title,
        "section": [{"title": r.title, "entry": [ref("DiagnosticReport", r.id)]}],
    }
    resources = [
        comp,
        patient_resource(r.patient),
        organization_resource(r.facility),
        practitioner_resource(r.created_by),
        diagnostic_report_resource(r),
    ] + [observation_resource(o, r) for o in r.observations]
    return {
        "resourceType": "Bundle",
        "id": f"report-{r.id}",
        "identifier": {"system": f"{ID_SYSTEM}/report-bundle", "value": f"report-{r.id}"},
        "type": "document",
        "timestamp": iso(utcnow()),
        "entry": [{"fullUrl": f"{FHIR_BASE_URL}/{x['resourceType']}/{x['id']}", "resource": x} for x in resources],
    }


# ---------- doctor consultation (OP consultation record) ----------
# Vital signs: field -> (LOINC code, display, UCUM unit). Blood pressure is a panel with two components.
VITALS = {
    "pulse": ("8867-4", "Heart rate", "/min"),
    "temperature": ("8310-5", "Body temperature", "Cel"),
    "spo2": ("59408-5", "Oxygen saturation in Arterial blood by Pulse oximetry", "%"),
    "weight": ("29463-7", "Body weight", "kg"),
}


def loinc_code(code, display):
    return {"coding": [{"system": LOINC_SYSTEM, "code": code, "display": display}]}


def quantity(value, unit):
    return {"value": value, "unit": unit, "system": UCUM_SYSTEM, "code": unit}


def consultation_bundle(c):
    """A FHIR document Bundle for one consultation, shaped like an ABDM OP Consultation Record.

    Section codes are LOINC; complaints, diagnoses and medicines are free text until SNOMED CT and a
    drug terminology are integrated.
    """
    withdrawn = c.status == "entered-in-error"
    key = f"consult-{c.id}"
    subject, enc, doctor = ref("Patient", c.patient_id), ref("Encounter", key), ref("Practitioner", c.doctor_user_id)

    def condition_res(suffix, category_code, category_display, label, text):
        res = {
            "resourceType": "Condition", "id": f"{key}-{suffix}",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-category",
                                      "code": category_code, "display": category_display}], "text": label}],
            "code": {"text": text}, "subject": subject, "encounter": enc,
            "recordedDate": iso(c.visit_at), "recorder": doctor,
        }
        if withdrawn:
            res["verificationStatus"] = {"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "entered-in-error"}]}
        else:
            res["clinicalStatus"] = {"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]}
        return res

    def observation_res(suffix, code, display, category, **value):
        return {
            "resourceType": "Observation", "id": f"{key}-{suffix}",
            "status": "entered-in-error" if withdrawn else "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                      "code": category[0], "display": category[1]}]}],
            "code": loinc_code(code, display), "subject": subject, "encounter": enc,
            "effectiveDateTime": iso(c.visit_at), "performer": [doctor], **value,
        }

    encounter_res = {
        "resourceType": "Encounter", "id": key, "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
        "subject": subject, "participant": [{"individual": doctor}],
        "period": {"start": iso(c.visit_at)}, "serviceProvider": ref("Organization", c.facility_id),
    }
    complaint = condition_res("complaint", "problem-list-item", "Problem List Item", "Chief complaint", c.chief_complaint)
    diagnosis = condition_res("diagnosis", "encounter-diagnosis", "Encounter Diagnosis", "Diagnosis", c.diagnosis)

    vital_sign = ("vital-signs", "Vital Signs")
    findings = []
    if c.examination:
        findings.append(observation_res("exam", "29545-1", "Physical findings Narrative", ("exam", "Exam"),
                                        valueString=c.examination))
    if c.bp_systolic is not None:
        findings.append(observation_res(
            "bp", "85354-9", "Blood pressure panel with all children optional", vital_sign, component=[
                {"code": loinc_code("8480-6", "Systolic blood pressure"), "valueQuantity": quantity(c.bp_systolic, "mm[Hg]")},
                {"code": loinc_code("8462-4", "Diastolic blood pressure"), "valueQuantity": quantity(c.bp_diastolic, "mm[Hg]")},
            ]))
    for field, (code, display, unit) in VITALS.items():
        value = getattr(c, field)
        if value is not None:
            findings.append(observation_res(field, code, display, vital_sign, valueQuantity=quantity(value, unit)))

    meds = [{
        "resourceType": "MedicationRequest", "id": f"{key}-med-{m.id}",
        "status": "entered-in-error" if withdrawn else "active", "intent": "order",
        "medicationCodeableConcept": {"text": m.name}, "subject": subject, "encounter": enc,
        "authoredOn": iso(c.visit_at), "requester": doctor,
        "dosageInstruction": [{"text": " · ".join(x for x in (m.dosage, m.frequency, m.duration, m.instructions) if x)}],
    } for m in c.medications]

    follow_up = None
    if c.follow_up_date:
        follow_up = {
            "resourceType": "Appointment", "id": f"{key}-followup",
            "status": "entered-in-error" if withdrawn else "proposed", "description": "Follow-up visit",
            "requestedPeriod": [{"start": c.follow_up_date.isoformat()}],
            "participant": [{"actor": subject, "status": "needs-action"}, {"actor": doctor, "status": "accepted"}],
        }

    def entries(items):
        return [ref(x["resourceType"], x["id"]) for x in items]

    sections = [{"title": "Chief complaints", "code": loinc_code("10154-3", "Chief complaint Narrative - Reported"),
                 "entry": entries([complaint])}]
    if findings:
        sections.append({"title": "Physical examination", "code": loinc_code("29545-1", "Physical findings Narrative"),
                         "entry": entries(findings)})
    sections.append({"title": "Diagnosis", "code": loinc_code("29548-5", "Diagnosis Narrative"), "entry": entries([diagnosis])})
    if meds:
        sections.append({"title": "Medications", "code": loinc_code("57828-6", "Prescription list"), "entry": entries(meds)})
    if c.advice or follow_up:
        plan = {"title": "Advice and follow-up", "code": loinc_code("18776-5", "Plan of care note")}
        if c.advice:
            plan["text"] = {"status": "generated",
                            "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{html.escape(c.advice)}</div>'}
        if follow_up:
            plan["entry"] = entries([follow_up])
        sections.append(plan)

    comp = {
        "resourceType": "Composition", "id": key,
        "status": "entered-in-error" if withdrawn else "final",
        "type": loinc_code("11488-4", "Consult note"),
        "subject": subject, "encounter": enc, "date": iso(c.created_at),
        "author": [doctor, ref("Organization", c.facility_id)],
        "title": "OP consultation record", "custodian": ref("Organization", c.facility_id),
        "section": sections,
    }
    resources = ([comp, patient_resource(c.patient), organization_resource(c.facility), practitioner_resource(c.doctor),
                  encounter_res, complaint, diagnosis] + findings + meds + ([follow_up] if follow_up else []))
    return {
        "resourceType": "Bundle",
        "id": f"consultation-{c.id}",
        "identifier": {"system": f"{ID_SYSTEM}/consultation-bundle", "value": f"consultation-{c.id}"},
        "type": "document",
        "timestamp": iso(utcnow()),
        "entry": [{"fullUrl": f"{FHIR_BASE_URL}/{x['resourceType']}/{x['id']}", "resource": x} for x in resources],
    }


def validate(resource):
    """Return a list of readable error strings (empty list = valid base R4)."""
    errors = []
    items = [e["resource"] for e in resource.get("entry", [])] if resource["resourceType"] == "Bundle" else []
    for res in [resource] + items:
        cls = FHIR_CLASSES.get(res.get("resourceType"))
        if cls is None:
            errors.append(f"Unsupported resourceType {res.get('resourceType')}")
            continue
        try:
            cls(res, strict=True)
        except FHIRValidationError as e:
            errors += [f"{res['resourceType']}/{res.get('id')}: {err}" for err in e.errors]
    if items:
        # Every reference inside a document bundle must point to an entry of the bundle.
        present = {f"{r['resourceType']}/{r['id']}" for r in items}
        for r in items:
            for target in find_references(r):
                if target not in present:
                    errors.append(f"{r['resourceType']}/{r['id']}: reference {target} is not in the bundle")
        if items[0]["resourceType"] != "Composition":
            errors.append("Bundle: a document bundle must start with a Composition")
    return errors


def find_references(value):
    if isinstance(value, dict):
        found = [value["reference"]] if isinstance(value.get("reference"), str) else []
        for v in value.values():
            found += find_references(v)
        return found
    if isinstance(value, list):
        return [x for v in value for x in find_references(v)]
    return []


def with_validation(resource):
    errors = validate(resource)
    return {
        "resource": resource,
        "validation": {
            "valid": not errors,
            "errors": errors,
            "checked_against": "Base FHIR R4 (4.0.1) structures via fhirclient; not ABDM IG profiles",
        },
    }


def capability_statement():
    return {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": iso(utcnow()),
        "kind": "instance",
        "software": {"name": "ABDM Connect"},
        "implementation": {"description": "ABDM Connect FHIR R4 read API", "url": FHIR_BASE_URL},
        "fhirVersion": "4.0.1",
        "format": ["json"],
        "rest": [{
            "mode": "server",
            "security": {"description": "Bearer JWT required. Hospitals read data only via consent-checked retrieval."},
            "resource": [{"type": t, "interaction": [{"code": "read"}]}
                         for t in ("Patient", "Observation", "DiagnosticReport")],
        }],
    }
