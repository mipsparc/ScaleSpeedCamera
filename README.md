# ScaleSpeedCamera
興味を持っていただきありがとうございます。
このソフトは、Z・N・HOゲージ(要望があれば他にも)の実車に換算した速度(スケールスピード)をカメラで測定するものです。
なお、本ソフトは現在テストバージョンですので、いろいろと整っていない点もございます。
どうぞご了承いただけますよう、よろしくお願いします。

## Windows版ダウンロード方法
画面右側のReleasesをクリックして、もっともバージョンの大きいものをダウンロードしてください。

## 動作環境
Linux, Windows 10 64bitでの動作が確認されています。
上記環境で正常に動作しなかった場合は、Twitterの @mipsparc にてご報告をお願いします。
その他の環境については、要望が多ければ対応します。

## 本ソフトウェアのライセンス
MITライセンスとします。

## Linuxで動かす場合
Python3がはじめから入っているUbuntuなどでは、
- $ sudo apt-get install libdmtx0b
- $ pip3 install pylibdmtx
- $ pip3 install opencv-contrib-python
- $ pip3 install pyzbar

で動くはずです。発話をするなら
- $ sudo apt-get install open-jtalk open-jtalk-mecab-naist-jdic hts-voice-nitech-jp-atr503-m001
をする必要があります。

## 作者
mipsparc
Twitter: https://twitter.com/mipsparc
Mail: mipsparc@gmail.com
お気軽にご連絡ください
