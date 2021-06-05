# ISAC-SIMO Documentation
We use MkDocs for building and generating the documentations. MkDocs is a fast, simple and downright gorgeous static site generator that's geared towards building project documentation. Documentation source files are written in Markdown, and configured with a single YAML configuration file.

[Learn About MkDocs](https://www.mkdocs.org/)

The Markdown files listed above are used for their specific documentation. They can be edited and built into HTML documentation pages.

## Building Documentation:
MkDocs and a template need to be installed first using `pip`
```sh
pip install mkdocs
pip install mkdocs-material
```

From the root our repository, we need to run:
```sh
mkdocs build
```
This, will build the documentation as HTML and saves them in the `site` directory. Note that we use some mkdocs markdown extensions that can be viewed in `mkdocs.yml` file.

The Documentation is hosted at: [https://www.isac-simo.net/docs/](https://www.isac-simo.net/docs/)

## All Documentation:
- [Documentaion Home](https://www.isac-simo.net/docs/)
- [Getting Started](https://www.isac-simo.net/docs/getting-started/)
- [Web Application](https://www.isac-simo.net/docs/web-application/)
- [Mobile Application](https://www.isac-simo.net/docs/mobile-application/)
- [Developer Guide](https://www.isac-simo.net/docs/developer-guide/)
- [Mobile API Guide](https://www.isac-simo.net/docs/mobile-api-guide/)
- [Lite Dashboard](https://www.isac-simo.net/docs/lite-dashboard/)
- [External Integration](https://www.isac-simo.net/docs/integration/)
