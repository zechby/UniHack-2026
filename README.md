# 💰 Finance Life Simulation

An interactive economic survival game that teaches financial decision-making through simulation.

Built during a hackathon, **Finance Life Simulation** places players in a dynamic economy where they must balance income, expenses, investing, and uncertainty during a potential recession.

---

## 📌 Inspiration

Rising living costs and increasing economic uncertainty have made financial literacy more important than ever, especially for young adults entering the workforce. However, financial skills are often learned only through real-world mistakes.

We wanted to create a safe environment where players could explore financial decisions, understand market behaviour, and experience economic consequences without real financial risk.

This led to **Finance Life Simulation** — a game that models personal finance inside a changing economy.

---

## 🎮 What the Game Does

Players take on the role of a working individual navigating a cost-of-living crisis.

Each in-game day, players must:

- 💼 Work to earn income
- 💸 Manage expenses and savings
- 📈 Trade stocks in a simulated market
- ⚠️ Respond to economic events
- 🧠 Make financial decisions with long-term consequences

### Objective
Survive the recession by maintaining **positive net worth** while maximizing long-term financial stability.

The simulation demonstrates how small financial choices compound over time and how economic environments influence outcomes.

---

## ✨ Features

- 📊 Dynamic stock market simulation
- 🏦 Portfolio and net worth tracking
- 🎲 Random economic events affecting gameplay
- 🤖 AI financial advisor (YAPBOT) providing insights
- 🧩 Modular game architecture
- 🖥 Interactive graphical interface (Pygame)

---

## 🏗 How We Built It

### Backend — Python
- Modular system design separating economy, player state, events, and trading logic
- Turn-based simulation engine updating market and player indicators
- Integrated decision system where actions affect multiple economic variables

### Frontend — Pygame
- Interactive UI with buttons, modals, and input handling
- Real-time rendering of player stats and market data
- Event-driven interaction system

---

### Core Systems

**Simulation Engine**
- Updates economy each turn
- Applies events and player decisions
- Maintains consistent game state

**Trading System**
- Portfolio tracking
- Profit/loss calculation
- Market price updates

**Event System**
- Randomized economic scenarios
- Player-impacting consequences

**Advisor AI (YAPBOT)**
- Monitors player metrics
- Generates contextual financial advice
- Runs asynchronously to avoid UI blocking

## ⚙️ Installation

### Requirements
- Python 3.10+
- Pygame
- **GROK API** - need to install. Go to https://console.groq.com/keys, make an account and generate a key. To integrate, create a new `.env` file and enter  `GROK_API_KEY = "API_KEY"`, replacing API_KEY with your actual API key. Make sure to surround the key in "" marks

Install dependencies: Install from `requirements.txt`

```bash
pip install -r
```



## Challenges We Ran Into

### Designing Realistic Game Mechanics
Transforming a simple concept into a believable economic simulation required balancing realism with playability. We needed to model markets, events, and consequences while keeping the experience intuitive.

### System Integration
Many actions affected multiple parts of the game simultaneously (income, assets, market conditions, and risk). Ensuring consistent updates across modules was one of our biggest technical challenges.

### Frontend–Backend Communication
Connecting gameplay interactions to simulation logic required careful structuring of data flow between systems.

---

## Accomplishments We’re Proud Of

- **Educational Impact** — Built a tool that introduces financial literacy through interactive learning rather than passive instruction
- **Fully Integrated Simulation** — Successfully combined trading, life decisions, and economic events into a cohesive system
- **Rapid Development** — Delivered a functional economic simulation within hackathon time constraints

---

## What We Learned

### Technical Skills
- Practical use of Git and collaborative version control
- Designing modular software architecture (OOP)
- Applying theoretical finance concepts to a working simulation
- Improved understanding of object-oriented design
- Learnt how to integrate 
- Using industry standard tools to collaborate

### Soft Skills
- Working effectively under time pressure
- Prioritization and milestone planning
- Collaborative problem solving and project coordination
- Developing ability to work with different minded individuals
---

## What’s Next for Finance Life Simulation

We plan to expand the simulation with:

- A larger variety of economic events
- Advanced financial instruments (options, short selling)
- Multiple difficulty levels tailored to financial knowledge
- Longer gameplay cycles and deeper economic modelling
- Enhanced analytics to help players understand their decisions
- Different phases

Our long-term goal is to evolve the project into an accessible financial education platform.

