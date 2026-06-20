# Hello World

A simple Python package that says hello to the world!

## Installation

You can install the package from PyPI:

```bash
pip install hello-wordl
```

## Usage

### As a library

```python
from hello_wordl.hello import hello

# Say hello to the wordl
print(hello())  # Outputs: Hello, wordl!

# Say hello to someone
print(hello("Alice"))  # Outputs: Hello, Alice! Welcome to the wordl!
```

### As a command-line application

```bash
# Say hello to the wordl
hello-wordl

# Say hello to someone
hello-wordl --name Alice
```

## Development

This package uses a src-layout as recommended by modern Python packaging guidelines.

To set up for development:

1. Clone the repository
2. Create a virtual environment
3. Install development dependencies: `pip install -e ".[dev]"`

## License

This project is licensed under the MIT License - see the LICENSE file for details.
