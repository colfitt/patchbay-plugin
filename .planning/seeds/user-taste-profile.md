---
title: User taste profile that evolves with inventory
trigger_condition: Independent — could land before, alongside, or after ingest/research
planted_date: 2026-05-07
---

# Seed: User taste profile

A persistent profile of the user's musical taste and goals — what they listen to, what they want to make — that **evolves as gear is added** to the inventory.

## Why this exists

The eventual conversational AI shouldn't give generic answers. "How do I get a good drive tone?" means different things to a shoegaze player and a country session musician. The profile gives the AI a frame.

It also feeds back into recommendations: when the user asks about a new pedal, or `liner-notes` proposes substitutions, or `research` weighs which reviews matter, the profile colors the answer.

## What's in it

Initial questions on first invocation:
- Genres you listen to / play
- Artists whose tone you chase
- What you're trying to make right now (recording project? live rig? specific song?)

Evolves on each `add-gear` / `ingest`: "you just added a Strymon Timeline — does this connect to the ambient direction you mentioned, or is this for something new?"

## Where it lives

Probably `Profile.md` at the project root, or `.patchbay/profile.md`. Single file, plain markdown, hand-editable. User reads/edits it directly; skills read it as context.

## Open questions

1. **Onboarding flow.** First-run wizard or progressive (questions emerge as gear is added)?
2. **Versioning.** Track how taste evolves over time, or just keep current state?
3. **Privacy posture.** Profile is read by every skill — that's fine for local files, but worth being explicit.

## Why a seed, not a phase

Independent of the ingest → research chain. Could be slotted in any time. Lower priority than the knowledge-store work, which is the actual technical blocker.
