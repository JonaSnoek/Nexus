# Contributing to NEXUS

Thank you for your interest in contributing to NEXUS! This document provides guidelines and information for contributors.

## Getting Started

1. **Fork the repository** on GitHub.
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/nexus.git
   cd nexus
   ```
3. **Set up the development environment**:
   ```bash
   cp .env.example .env
   sudo bash install.sh
   ```

## Development Workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes.
3. Write or update tests as needed.
4. Ensure all tests pass.
5. Commit with a clear, descriptive message.
6. Push to your fork and open a Pull Request.

## Code Style

### Python (Backend)
- Follow PEP 8.
- Use type hints.
- Use meaningful variable and function names.
- Keep functions focused and concise.
- Add docstrings for public functions.

### TypeScript (Frontend)
- Follow the project's ESLint and Prettier configurations.
- Use functional components with hooks.
- Keep components small and focused.

### Shell Scripts
- Use `#!/bin/bash`.
- Use `set -euo pipefail` for error handling.
- Quote all variables.
- Use functions for repeated logic.

## Commit Messages

- Use the present tense ("Add feature" not "Added feature").
- Use the imperative mood ("Fix bug" not "Fixes bug").
- Keep the subject line under 72 characters.
- Reference issues and pull requests where relevant.

## Pull Requests

1. Fill in the PR description with what changed and why.
2. Link any related issues.
3. Ensure CI passes before requesting review.
4. Be responsive to review feedback.

## Reporting Issues

- Use the GitHub issue tracker.
- Include steps to reproduce.
- Include environment details (OS, Docker version, etc.).
- Include relevant logs.

## Code of Conduct

- Be respectful and inclusive.
- Focus on constructive feedback.
- Welcome newcomers and help them get started.

## License

By contributing to NEXUS, you agree that your contributions will be licensed under the MIT License.
