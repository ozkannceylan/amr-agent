# m5-75 — the owner's study documents

    gate:                M5
    agents:              one per document, each with exactly one deliverable
    goal:                Give the owner documents they can master their own system from, in time to defend it on stage against detailed questions about safety PLCs.
    invariants_touched:  none. These documents describe; they change nothing.
    deliverable root:    C:\Users\ozkan\OneDrive\Documents\MyNotes\projects\active\amr-agent\study\
    forbidden:
      - writing anything inside the repository, including evidence or reports
      - stating anything not traceable to a committed file. If it is not in the repo, say so
      - claiming or implying an achieved PL, Category, SIL or PFH
      - smoothing over a gap, a stand-in or a known defect to make the story cleaner

---

## 1. Why these exist, and what that means for how they are written

The owner is presenting this system **as its author**, and expects **detailed
questions about safety PLCs**. These are not summaries. They are **study
documents**: written so that after reading one, the owner can answer a hostile
question without looking anything up.

That has three consequences, and they outrank style:

1. **Every claim is traceable.** Name the file and the section. A reader who
   doubts a sentence must be able to open the artefact behind it in one step.
2. **Anticipate the questions and answer them in the document.** After each
   mechanism, ask what a sharp reviewer would push on, and answer it. A section
   that only describes leaves the owner defenceless.
3. **State the limits with the same weight as the capabilities.** The safety
   input path is a **labelled stand-in**; the F-program's data arrives as
   standard data; no PL, Category, SIL or PFH is claimed anywhere. A document
   that hides this sets the owner up to be caught. One that states it plainly
   turns the hardest question into a prepared answer.

## 2. Language

**Turkish prose, English technical terms kept in English** — `safety`,
`F-program`, `latch`, `monitored reset`, `envelope`, `demand`, `stand-in`,
`protective field`, `PLr`. This matches the owner's existing vault documents
(`F-PLC-Akisi-Nasil-Calisiyor-2026-08-06.md`) and how they work.

Do not translate a term and then use the translation as if it were the term. The
owner will hear the English word on stage.

## 3. Shape

- **Step by step**, as the owner asked. Numbered where there is an order.
- **A table beats a paragraph** wherever there is structure.
- **Diagrams where the shape matters** — mermaid, since the vault renders it.
- Open with a **one-screen summary**: what this layer is, what it owns, what it
  must never do.
- Close with **"muhtemel sorular"** — the questions a reviewer will actually
  ask, each with the answer and the artefact behind it.

## 4. The six documents

| File | Subject | Model |
|---|---|---|
| `01_safety_plc.md` | The F-program: every safety function built at M5, step by step | fable |
| `02_standart_plc.md` | The standard program: what was coded and why it is separate | fable |
| `03_ros2.md` | The ROS 2 side: how the vehicle stack is composed | fable |
| `04_hmi.md` | The commissioning HMI | opus |
| `05_writer.md` | The stand-in writer and its bench panel | opus |
| `06_gazebo.md` | The simulation environment | opus |

**Note on numbering:** the owner's message numbered Gazebo `03`, which collides
with the ROS 2 document. It is `06_gazebo.md` here. Anything else would
overwrite a file the owner asked for.

## 5. Where the truth lives

Start from these; follow what they cite rather than guessing.

- `CLAUDE.md` — the contract, the thirteen invariants, the topology
- `plc/forklift-safety/SPEC.md` — the F-program
- `plc/forklift/SPEC.md` — the standard program
- `plc/forklift/TIA-BUILD-PROCEDURE.md` and `TIA-FIX-PROCEDURE.md` — what was
  actually built on the CPU, step by step, with the signatures
- `docs/safety/SRS.md`, `docs/safety/SLS-STANDARDS-BASIS.md`,
  `docs/safety/PL-SCENARIOS.md`
- `docs/interfaces/opcua-nodes.md`, `docs/interfaces/bridge-design.md`
- `docs/VALIDATION-M5.md` — what has actually been demonstrated, with its n
- `docs/adr/` — 0011 (the claim boundary), 0014, 0015, 0016
- `docs/LESSONS.md` — the mistakes, which are often the best explanations
- the layer's own README and evidence files

## 6. Working discipline

- **Write the document as you go.** Do not hold it all for the end.
- If two sources disagree, **say which is authoritative and why** — that
  disagreement is itself something the owner should know before being asked.
- **Do not commit.** These live in the owner's vault, outside the repository.
