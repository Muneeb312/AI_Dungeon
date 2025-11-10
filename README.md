# AI_Dungeon

This is a simple, text-based adventure game. It uses Ollama to power a Game Master AI, while a Python engine enforces a set of rules defined in `rules.json`.

The game is designed to be free-form: you can type any action (e.g., "I look at the symbols" or "I try to open the door") and the AI will interpret it.

## Setup

### Prerequisites
* [Python](https://www.python.org/downloads/)
* [Ollama](https://ollama.com/) (must be installed and running)

### 1. Install Ollama and Pull a Model

First, make sure Ollama is installed and running on your system.

Then, you need to pull a model for the game to use. The default model being used is `llama3.1:8b`.

Open your terminal and run:
```bash
ollama pull llama3.1:8b
```
Then you can run main.py to play the game!
