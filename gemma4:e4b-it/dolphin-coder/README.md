ollama create dolphin-gemma-4b -f Modelfile
<br>
권한 오류 발생시
<br>
```bash
# 1. Ollama 프로세스가 G드라이브를 쥐고 있어서 마운트 해제가 튕기는 것을 방지
sudo systemctl stop ollama
sudo pkill ollama

# 2. 작업 중인 G드라이브 폴더 밖(리눅스 홈)으로 잠시 이동
cd ~

# 3. 기존 G드라이브 마운트 해제 (우분투 비밀번호 입력)
sudo umount /mnt/g

# 4. 핵심 트러블슈팅: 리눅스 권한(metadata)을 허용하는 옵션을 켜서 재마운트
sudo mount -t drvfs G: /mnt/g -o metadata

# 5. Ollama 서비스 다시 가동
sudo systemctl start ollama

# 6. 원래 작업 폴더로 복귀하여 대망의 마지막 빌드 재시도
cd /mnt/g/ollama
ollama create dolphin-gemma-4b -f Modelfile
```

<br>
ollama run dolphin-gemma-4b
