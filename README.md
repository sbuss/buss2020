[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

# buss2020
My run for SF DCCC in 2020

## Automatic NetFile

First install chromedriver: https://chromedriver.chromium.org/downloads

Then:

```sh
pipenv sync
pipenv shell
python selen.py /path/to/actblue-contributions.csv --method people
python selen.py /path/to/actblue-contributions.csv --method donations
python selen.py /path/to/actblue-contributions.csv --method fees
```
