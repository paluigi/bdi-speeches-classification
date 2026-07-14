# Banca d'Italia Speeches Classification

An NLP and Machine Learning pipeline designed to scrape, preprocess, analyze, and classify speeches delivered by th Governor and members of the Governing Board of the **Bank of Italy (Banca d'Italia)** using Large Language Models. This repository provides end-to-end workflows to extract valuable central banking insights, categorize texts by policy topics, and perform sentiment or thematic classification.

---

## 🚀 Features

* **Data Extraction:** Scrapers and parsers tailored for the official Banca d'Italia portal.
* **Classification Pipeline:** Fully configurable classification using LLMs and the `ollama-classifier` library.

---

## 🛠️ Tech Stack & Tooling

This project leverages modern Python development tools:
* **Package Manager:** [uv](https://github.com/astral-sh/uv) (fast, modern Python package installer and resolver)
* **LLM handler:** `ollama-classifier` 
* **Data Processing:** `pandas`, `TinyDB`, `beautifulsoup4`
* **Environment Management:** Python `3.10+` with `.env` configuration


