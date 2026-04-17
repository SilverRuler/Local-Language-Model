success but inefficient
<br>

```bash
sudo nano /etc/wsl.conf

[automount]
options = "metadata"

wsl --shutdown

ollama create my-dolphin-test -f Modelfile
```
