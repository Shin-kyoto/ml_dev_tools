# Compare video result

- Code for generate video to compare results from detector

## How to use

### environment setup

```sh
sudo apt install imagemagick
```

### modify imagemagick profile

```sh
sudo nano /etc/ImageMagick-6/policy.xml
```

comment out the line including this

```xml
  <policy domain="path" rights="none" pattern="@*"/>
```

### setup uv venv

```sh
~/ml_dev_tools/AWML_dev_tools/compare_video_result
❯ uv venv

~/ml_dev_tools/AWML_dev_tools/compare_video_result
❯ source .venv/bin/activate
```

```sh
uv pip install .
```

### fill config/base.yaml

Open and fill [config](./config/base.yaml).

### run command

```sh
python src/compare_video_result/cli.py config/base.yaml
```