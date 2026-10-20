# Scarlet Crusade

An adventure module for Bane of Azeroth.

## Optimize PDF

To build the docker image:

```bash
docker build -f Dockerfile.pdf-optimizer -t boa-pdf-optimizer .
```

To optimize the pdf:

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/data" \
  boa-pdf-optimizer \
  "Bane of Azeroth - The Scarlet Crusade.pdf" \
  "Bane of Azeroth - The Scarlet Crusade (Optimized).pdf"
```
