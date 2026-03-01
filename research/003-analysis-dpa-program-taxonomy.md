---
type: analysis
created: 2026-03-01T19:30:00
sessionId: S20260301_1800
source: cursor-agent
description: Three-axis taxonomy for DPA program discovery — funding entity, benefit structure, eligibility persona
---

# DPA Program Taxonomy — Discovery Classification Framework

## Purpose

This taxonomy provides the shared vocabulary for the hierarchical graph discovery engine, seed parser, program enumerator prompts, and coverage assessment. All three axes are used at different pipeline stages.

## Axis I — Funding Entity (the "Who")

Drives **L0/L1 discovery search** — determines where to look and what web queries to run.

| Code | Category | Examples | Discovery Strategy |
|------|----------|----------|-------------------|
| `federal` | Federal Government | HUD, VA, USDA, FHA | Well-covered by LLM training data; grounding optional |
| `state_hfa` | State Housing Finance Agencies | CalHFA, SONYMA, NJHMFA, IHDA | Partially covered; grounding recommended for current program lists |
| `municipal` | Municipal / Local Government | City/County programs, CDBG-funded, HOME-funded | Poorly covered; grounding required — search per city/county |
| `employer` | Private / Employer-Sponsored (EAH) | Hospital systems, universities, corporations | Zero coverage in training data; grounding required |
| `nonprofit` | Non-Profit / NGO | NACA, Habitat for Humanity, CDFIs, NeighborWorks | Zero coverage; grounding required — search CDFI Fund, NeighborWorks directory |
| `tribal` | Tribal Housing Authorities | Section 184, tribal HAs | Minimal coverage; grounding required |
| `gse` | Government-Sponsored Enterprises | Fannie Mae HomeReady, Freddie Mac Home Possible/HomeOne | Well-covered by training data |

### Recommended Search Queries by Entity Type

- **state_hfa**: `"List all State Housing Finance Agency second mortgage programs in {state} for 2026"`
- **municipal**: `"city-level down payment assistance grants for {city, state} funded by CDBG or HOME funds"`
- **nonprofit**: `"non-profit homeownership programs in {region} that offer silent second mortgages"`
- **employer**: `"employer-assisted housing program {city} hospital university"`
- **tribal**: `"Section 184 tribal housing authority homebuyer assistance {state}"`

## Axis II — Benefit Structure (the "How")

Drives **program classification and dedup** — prevents collisions between different program types from the same entity.

| Code | Category | Description |
|------|----------|-------------|
| `grant` | Direct Subsidy (Grant) | Non-repayable funds |
| `forgivable_lien` | Forgivable Second Mortgage | Disappears after X years of residency |
| `deferred_lien` | Deferred Second Mortgage | No interest or payments until sale/refi |
| `repayable_lien` | Repayable Second Mortgage | Low-interest loan paid alongside primary mortgage |
| `mcc` | Mortgage Credit Certificate | Tax credit reducing federal income tax liability |
| `tax_abatement` | Tax Abatement | Property tax reduction for set period |
| `rate_subsidy` | Interest Rate Subsidy | Below-market rate from state HFA |
| `renovation` | Renovation/Energy Loan | FHA 203k, HomeStyle, GreenCHOICE — combines purchase + rehab |

## Axis III — Eligibility Persona (the "Target")

Drives **seed routing** — determines which seeds are injected at which discovery node.

| Code | Category | Typical Gate | Examples |
|------|----------|-------------|----------|
| `fthb` | First-Time Homebuyer | No prior ownership in 3 years | Most state HFA programs |
| `veteran` | Veterans / Military | VA eligibility, active duty, surviving spouse | VA Loans, state veteran bonuses |
| `occupation` | Occupational / Service-Based | Teacher, police, fire, EMS | Good Neighbor Next Door (GNND) |
| `lmi` | Low-to-Moderate Income | 80% or 120% of Area Median Income | Most DPA programs |
| `tribal` | Native American / Alaska Native | Tribal membership or AIAN status | HUD Section 184 |
| `demographic` | Demographic / Geographic | First-generation buyer, revitalization zone resident | Place-based programs |
| `property_specific` | Property-Specific | Fixer-upper, energy-efficient, manufactured housing | FHA 203k, GreenCHOICE |
| `general` | No Specific Gate | Open to all qualifying buyers | Conventional 97, HomeReady |

## Government-Backed Loan Programs (Reference)

These are the foundational loan products that DPA programs layer on top of:

| Program | Down Payment | Key Requirement |
|---------|-------------|-----------------|
| FHA Loans | 3.5% | Credit score 500-580 minimum |
| VA Loans | 0% | Veteran/active duty/surviving spouse |
| USDA Loans | 0% | Rural/suburban area, income limits |
| HUD Section 184 | Varies | American Indian/Alaska Native |
| Conventional 97 | 3% | PMI required |
| HomeReady (Fannie Mae) | 3% | Income limits (80% AMI) |
| Home Possible (Freddie Mac) | 3% | Income limits (80% AMI) |
| HomeOne (Freddie Mac) | 3% | No income limits |

## Common Synonyms and Search Terms

| Term | Synonyms / Aliases |
|------|-------------------|
| FTHB | First-Time Homebuyer, first-time buyer |
| DPA | Down Payment Assistance, down payment help |
| Grant | Gift funds, non-repayable assistance |
| Forgivable Loan | Silent second, deferred forgivable, soft second |
| MCC | Mortgage Credit Certificate, mortgage tax credit |
| Conventional 97 | 3% down conventional, 97% LTV |
| HFA | Housing Finance Agency, housing finance authority |
| CDBG | Community Development Block Grant |
| HOME | HOME Investment Partnerships Program |
| CDFI | Community Development Financial Institution |
| EAH | Employer-Assisted Housing |
| NACA | Neighborhood Assistance Corporation of America |
| GNND | Good Neighbor Next Door |
| LMI | Low-to-Moderate Income |
| AMI | Area Median Income |

## Usage in Pipeline

### Seed Parser
- Classify each seed record into `funding_entity`, `benefit_type`, and `eligibility_persona`
- Use keyword matching on `name`, `administering_entity`, and `benefits` fields
- Explicit `program_type` field in CSV/JSON overrides inference

### Discovery Graph Engine
- L0: Discover entities across all `funding_entity` categories
- L1: For each entity, inject seeds matching that entity's `eligibility_persona`
- L2: Classify discovered programs by `benefit_type` for dedup
- L3: Gap fill using unmatched seeds, prioritized by underrepresented `funding_entity` categories

### Coverage Assessment
- Report coverage by all three axes
- Flag categories with zero programs as high-severity gaps
- Compare discovered programs against seed file by `funding_entity` and `eligibility_persona`

## DFW Tags

`#track/dpa-v3-discovery` `#type/taxonomy` `#source/session-S20260301`
