# Builder Knower
Know thy build environment

## How to build

Edit setup.py with changes and bump up version
- `rm -rf builderknower.egg-info/ dist/ build/`
- `python3 setup.py sdist bdist_wheel`
- `vim dist/builderknower-0.1.[xx].tar.gz` -- patch out the distwheel stuff that breaks it so that it will work when actually installing
- `twine upload dist/*` - will ask for a token



