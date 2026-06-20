# Auto-Scrubber

Auto-Scrubber is a Python package designed to automate the process of data scrubbing. It provides a set of tools and utilities to clean, preprocess, and normalize data in various formats such as CSV, JSON, and SQL databases.

## Installation

You can install Auto-Scrubber via pip:

```bash
pip install auto-scrubber
```

## Features

- Automated cleaning of data with various data sources (databases, CSV files, JSON files, etc.)
- Support for multiple data formats (CSV, JSON, SQL, etc.)
- Customizable data cleaning rules
- Integration with popular data analysis libraries like pandas and numpy
- Export cleaned data in various formats

## Usage

Here's a basic example of how to use Auto-Scrubber:

```python
from auto-scrubber import Scrubber
```

# Create a new scrubber
scrubber = Scrubber()

# Define cleaning rules
scrubber.add_rule('remove_nulls')
scrubber.add_rule('trim_whitespace')
scrubber.add_rule('normalize_case')

# Apply the scrubber to a DataFrame
cleaned_df = scrubber.clean(dataframe)

# Save the cleaned data as a CSV
cleaned_df.to_csv("cleaned_data.csv")

In this example, `dataframe` is a pandas DataFrame containing the data you want to clean.


## License

Auto-Scrubber is licensed under the MIT license. See the [LICENSE](LICENSE) file for details.

