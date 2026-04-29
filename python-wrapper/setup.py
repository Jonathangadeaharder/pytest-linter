from setuptools import setup, find_packages

setup(
    name="pytest-linter",
    version="0.1.0",
    description="Fast, tree-sitter-powered test smell detector for pytest",
    long_description=open("../README.md").read(),
    long_description_content_type="text/markdown",
    author="Jonathan Gadea Harder",
    license="MIT",
    url="https://github.com/Jonathangadeaharder/pytest-linter",
    packages=find_packages(),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "pytest-linter=pytest_linter_py.wrapper:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Testing",
    ],
)
