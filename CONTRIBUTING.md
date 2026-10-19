# Contributing to VidShrink

First off, thank you for considering contributing to **VidShrink**! It is people like you that make VidShrink such a great utility for the community.

## 🛠 Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USER/VidShrink.git
   cd VidShrink
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install development dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   # Or using editable pip install:
   pip install -e .[dev]
   ```

4. **Run the application**:
   ```bash
   python run.py
   ```

## 🧪 Running Tests

Before submitting any Pull Request, ensure that all tests pass:

```bash
pytest
```

On headless Linux systems, run with:
```bash
QT_QPA_PLATFORM=offscreen pytest
```

## 📦 Building the Executable

To build the standalone Windows `.exe` locally:

```bash
python scripts/build.py
```

The output binary will be located in `dist/VidShrink.exe`.

## 💡 Submitting Changes

1. Fork the repo and create your branch from `main`:
   ```bash
   git checkout -b feature/my-cool-feature
   ```
2. Write clean, readable code and maintain documentation integrity.
3. Add unit tests for your changes where applicable.
4. Open a Pull Request referencing any related issues.
