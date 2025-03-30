# Twitter
X-Assistant

# venv
```
# Create venv
python3 -m venv venv
# Activate venv
source venv/bin/activate
# Exit venv
deactivate
```

# Install
```
pip install --upgrade pip
pip install -r requirements.txt
```

# X 账号文件
```
cd x-visit/
python fun_encode.py --file_in='datas/account/account.csv.sample' --file_ot='datas/account/encrypt.csv.sample' --idx=2 --key='ak6UVCToc32H9#mSAMPLE'

```

# Run
```
cd x-visit/
cp conf.py.sample conf.py
cp datas/account/encrypt.csv.sample datas/account/encrypt.csv
# modify datas/account/encrypt.csv
python xvisit.py
```
