# TrackWise AI - Model Card & Reflection

Building an AI-driven financial product requires moving beyond simply "making it work" and focusing heavily on responsibility and safety.

## 1. Limitations and Biases
The system's primary limitation is its dependency on Western/US-centric merchant naming conventions. While it thrives at categorizing "UBER" or "STARBUCKS", it might miscategorize niche, localized, or culturally specific vendors it wasn't extensively trained on. Additionally, as an LLM, Claude has innate limitations with complex arithmetic, which limits the mathematical complexity the Budget Planner can reliably output without Python fallback logic.

## 2. Potential Misuse & Prevention
A significant risk is users blindly trusting the AI's financial advice and making harmful cuts to essential livelihood expenses. To prevent this, I explicitly hard-coded safety constraints into the System Prompt: the Agent is strictly forbidden from ever suggesting cuts to *Rent/Housing* or *Income*. Furthermore, the UI acts as a guardrail by forcing a **Human-in-the-Loop** review—explicitly flagging any recommended cut over 50% with a visual "⚠️ Ambitious" warning badge so the user maintains final authority.

## 3. Surprises During Reliability Testing
While running my `reliability_check.py` script, I was incredibly surprised by how much LLMs struggle with basic structural formatting (like returning pure JSON) when lacking a strict system schema. However, I was equally surprised that once `temperature=0` and proper formatting constraints were applied, Claude's 3-run consistency and accuracy hit a perfect 100% on the benchmark transactions, proving that LLMs can be highly deterministic if engineered correctly.

## 4. Collaboration with AI
Building this project involved extensive pair-programming with AI, which proved to be a mixed bag:
* **Helpful Instance:** When struggling to conceptualize the "Agentic Workflow," the AI assistant elegantly suggested breaking the Budget Planner into a 4-step process (Plan → Act → Check → Output). This architectural suggestion elevated the tool from a basic chatbot predicting numbers into a self-verifying, advanced automation pipeline.
* **Flawed Instance:** During the UI polish phase, the AI suggested implementing a custom Javascript-animated cursor and appended `cursor: none;` to the global CSS. This caused severe usability issues, hiding the native system mouse and creating a disjointed, laggy experience. I had to intervene, parse the CSS to remove the rule, and restore the native hardware cursor to prioritize accessibility over flashy UI.

Ultimately, this project profoundly shifted how I view applied Artificial Intelligence. I learned that building a robust AI product is less about prompt-engineering a magic answer, and vastly more about **system engineering**: creating robust pipelines, data validation loops, and putting human guardrails first.
