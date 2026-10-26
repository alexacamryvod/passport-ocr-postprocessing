# Passport OCR post-processing

Small, offline Python project that decides whether to accept or reject OCR predictions for Russian internal passports. An accepted record contains all ten fields; a rejected record asks for a new scan. The rule is intentionally conservative because the assignment penalizes a wrong acceptance more heavily than a rejection.

## Repository contents

```text

├── .gitignore
├── README.md
├── postprocess.py
├── report.md
├── validate.py
└── tests/
    └── test_postprocess.py
```

The repository includes the generated `answers.jsonl` because it is a required assignment deliverable. The original challenge data is not included; `.gitignore` excludes a local `data/` directory.

## Requirements

- Python 3.10 or newer
- No third-party packages; the implementation uses the Python standard library

## Run

With the supplied `data/` directory placed beside the script, run the command from the assignment:

```bash
python3 postprocess.py data/test_predictions.jsonl answers.jsonl
```

The challenge data is not committed to this repository. Alternatively, pass the full local path to `test_predictions.jsonl` as the first argument.

The input is JSONL with one OCR prediction per line. The output is JSONL with one decision per `doc_id`:

```json
{"doc_id":"te_00001","decision":"reject"}
```

Accepted records also include the ten normalized fields. The supplied `answers.jsonl` contains 2,000 decisions; with the current thresholds, 33 are accepted and 1,967 rejected.

## Decision rule

The script checks that all ten fields are present, field and character confidence exceed the configured thresholds, dates and identifiers have the expected shape, and the passport is valid on 2026-10-01. It then compares names, date of birth, sex, part of the passport number, and the subdivision-code suffix with the MRZ. It does not guess or rewrite uncertain OCR text: a failed check rejects the record.

Thresholds are at the top of `postprocess.py` (`MIN_FIELD_CONF` and `MIN_CHAR_CONF`). A lower threshold can increase acceptance and also increase false accepts. The MRZ subdivision-suffix check is specific to the supplied dataset format and should be reviewed before reusing this code on other sources.

## Tests and validation

Run unit tests on synthetic fixtures (no challenge data required):

```bash
python3 -m unittest discover -s tests -v
```

Evaluate the current rule on a reproducible split of the labeled training set:

```bash
python3 validate.py /path/to/data/train_predictions.jsonl /path/to/data/train_labels.jsonl
```

The default split uses seed 42 and assigns 75% to `fit` and 25% to `holdout`. Current result at character threshold 0.99: fit accepted 10/2,250 with 0 wrong accepts; holdout accepted 6/750 with 0 wrong accepts. These are very small accepted samples. In addition, the threshold was selected during earlier exploratory analysis of the full training set, so this split is diagnostic rather than a fully independent final estimate. Do not tune on the holdout result.

## Privacy and publication

The challenge predictions, labels, and generated answers contain names, dates of birth, and passport identifiers. Do not publish the data or `answers.jsonl` unless the dataset owner explicitly permits public release. For a public portfolio, share the code and synthetic tests; keep the assignment answers in a private submission repository if required.

The answers contain passport-derived names, dates of birth, and identifiers. The assignment asks for the answer file in the repository; use the visibility required by the employer and confirm that the supplied data may be shared there. Do not add the original predictions or labels unless explicitly permitted.

## Scope and limitations

This is a post-processor for an existing OCR model, not an OCR engine. The test set has no labels here, so the estimated zero test errors are not verified. The conservative rule accepts a small fraction of documents; report both coverage and wrong accepts when comparing changes.
