from setuptools import setup, find_packages


setup(
    name="my_project",  # The name of the project
    version="0.1.0",  # Version of your project
    packages=find_packages(),  # Automatically find and include packages
    install_requires=[  # Any external dependencies
        "requests",  # Example
    ],
    author="Wei-Hsin Hsu",
    author_email="cynthiabour@gmail.com",
    description="Ocstrator for Gas/liquid flow chemistry platform control system",
    long_description=open("README.md").read(),  # Read the content of README.md
    long_description_content_type="text/markdown",  # Content type of README
    url="https://github.com/",  # Project URL
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",  # Change if you're using a different license
        "Operating System :: OS Independent",
    ],
)