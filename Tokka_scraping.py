# -*- coding: utf-8 -*-
import time
import sys
import requests
from bs4 import BeautifulSoup
import re
import schedule
import time
import datetime

### このプログラムでは5chの特価スレからAmazonの商品IDの抽出を目的としています。
### クローリング性をもたせるため、スケジュール実行・スレの差分のみの抽出も備えていますが、
### 検証あまりしてないです。

### 設定値
url = "https://egg.5ch.net/jisaku/"
threadURL = "https://egg.5ch.net/test/read.cgi/jisaku/"
keyWord = "特価"
refreshBoard = 10 ### スケジュール実行時のスレ一覧の更新頻度
refreshThread = 1 ### スケジュール実行時のスレの更新頻度
TraceLog = 0
Debug = 0 ### デバッグモードではスケジュール実行せずに各関数を呼出す。
resThreshold = 20
checkingThreadList = []
checkingThreadData = []
checkingThreadIndex = 0
checkingThreadIndexPast = 0
checkingThreadID = 1572703263
checkingThreadIDPast = 1572703263
productList = []
productDetailsList = []
productListPast = []
productListDiff = []

def main():
	if Debug:
		get_ThreadList()
		get_Tread()
		### amazonへのアクセステストでBANされたので利用中止
		#check_Product()
		## 未着手。動きません。
		#access_Product()
	else:
		get_ThreadList()
		get_Tread()
		schedule.every(refreshBoard).minutes.do(get_ThreadList)
		schedule.every(refreshThread).minutes.do(get_Tread)
		while True:
			schedule.run_pending()
			time.sleep(1)

### この関数内では5chの指定した板にアクセスしスレッド一覧の取得から
### 条件にマッチするスレッドIDの取得までを実施する。
### スレッドIDはグローバル変数のcheckingThreadListに格納する。
### checkingThreadListは一次元配列のため[スレッドID0, スレタイ0, レス数0, スレッドID1,...]と続く。
def get_ThreadList():
	print("Getting 5ch board data:"+str(datetime.datetime.now()))
	### 5chの板名にスレッド一覧のサブディレクトリを連結し、スレ一覧を取得する。
	### 日本語が前提のため文字エンコードも合わせて実施。
	res= requests.get(url+"subback.html")
	res.encoding = res.apparent_encoding
	if TraceLog:
		print(res.text)
	
	### beautifulsoup4を使いパースを実行する。
	### まずはスレ一覧をHTMLとして、そのままbs4へと渡す。
	### パースルールとスレの選出は次の基準で実施する。
	### ①HTLMのaタグがリンク形式(href)かつスレッドID(数字10桁)が含まれている場合、
	### 　パースしリスト(href_elements)へと代入する。
	### ②パース結果が格納されたリストを1つずつチェックし、
	### 　keyWordに指定した文字が含まれたリストを選出する。
	### ③選出されたリストから、スレッドIDのみを取り出し、巡回するスレッドURLを生成する。
	### 　スレッドURL生成時には同時にレス数も取得し、レスが一定数(resThreshold)以下のスレは含めいない。
	bs = BeautifulSoup(res.text, 'html.parser')
	href_elements = bs.find_all(href=re.compile("\d{10}"))
	if TraceLog:
		print(href_elements)
		for href_element in href_elements:
			print(href_element)
	tokkaThreadList_elements = []
	for href_element in href_elements:
		match = re.search(keyWord, href_element.string)
		if match:
			### ここで取得した要素のパースを実行する。
			### 要素は[ダミー, スレッドID, スレタイ, レス数, ダミー]と分割される。
			temp = re.split('<a href="|/l50">\d{1,3}:\s|\s\(|\)</a>', str(href_element))
			if int(temp[3]) > int(resThreshold) and int(temp[3]) < 1001:
				tempList = [temp[1],temp[2],temp[3]]
				checkingThreadList.extend(tempList)
			if TraceLog:
				print(href_element)
				print(temp)
	if TraceLog:
		print(checkingThreadList)

### checkingThreadList内のスレッドからスレ情報をHTML形式で取得し、
### それをパースする処理を行う。名前、日付、レス内容の3つにパースする。
### それらパースされた内容を一次元配列(checkingThreadData)に格納する。
### checkingThreadDataは一次元配列のため[レスの名前0, レスの日付0, レスの内容0, レスの名前1,...]と続く。
def get_Tread():
	global checkingThreadIndex
	global checkingThreadIndexPast
	global checkingThreadID
	global checkingThreadIDPast
	print("Getting 5ch Thread data:"+str(datetime.datetime.now()))
	res= requests.get(threadURL+checkingThreadList[0]+"/")
	res.encoding = res.apparent_encoding
	if TraceLog:
		print(res.text)
	bs = BeautifulSoup(res.text, 'html.parser')
	threadNameDat = bs.find_all('span', class_="name")
	threadDateDat = bs.find_all('span', class_="date")
	threadMessageDat = bs.find_all('span', class_="escaped")
	for i in range(len(threadMessageDat)):
		tempThreadData = [threadNameDat[i].string,threadDateDat[i].string,threadMessageDat[i]]
		checkingThreadData.extend(tempThreadData)
		if TraceLog:
			print(threadNameDat[i].string)
			print(threadDateDat[i].string)
			print(threadMessageDat[i])
	checkingThreadIndexPast = checkingThreadIndex
	checkingThreadIndex = len(threadMessageDat)
	checkingThreadIDPast = checkingThreadID
	checkingThreadID = checkingThreadList[0]
	print("Thread:" + checkingThreadList[1] + ", Name:"+str(len(threadNameDat))+", Date:"+str(len(threadDateDat))+", Message:"+str(len(threadMessageDat)))
	
	get_Response()

### グローバル変数のcheckingThreadData内の書込みレスをチェックする。
### その中に特定の条件(amazonの商品ID)が含まれる場合に抽出する。
### 抽出した商品IDは一次元配列としてproductListに格納する。
def get_Response():
	global productList
	global productListDiff
	print("Checking Thread data:"+str(datetime.datetime.now()))
	print("レス数："+str(checkingThreadIndex)+" 前回のレス数："+str(checkingThreadIndexPast)+" スレッドID："+str(checkingThreadID)+" 前回のスレッドID："+str(checkingThreadIDPast))
	if TraceLog:
		for tempData in checkingThreadData:
			print(tempData)

	for i in range(int(len(checkingThreadData)/3)):
		regTemp = re.search(r'B0[0-9A-Z]{8}',str(checkingThreadData[i*3+2]))
		#print("Checking res number :", i)
		if bool(regTemp):
			#print(regTemp.group())
			productList.append(regTemp.group())
	### 商品IDを前回からの差分抽出を行う。
	#print(productList) 
	#print(productListPast)
	productListDiff = list(set(productList) - set(productListPast))
	
	view_Product()

### この関数ではproductListに含まれる商品IDを用いてamazonへとアクセスする。
### アクセス先から、商品名, 値段,URLを取得する。
### それら取得した情報はproductDetailsListの一次元配列として格納する。
def check_Product():
	for tempProduct in productList:
		time.sleep(10)
		res= requests.get("https://www.amazon.co.jp/dp/"+tempProduct)
		if res.status_code != requests.codes.ok:
			print("Not fount the product: "+str(tempProduct))
			if TraceLog:
				print(res.text)
			continue
		res.encoding = res.apparent_encoding
		bs = BeautifulSoup(res.text, 'html.parser')
		tempTitle = bs.find_all('span', id="productTitle")
		if bool(bs.find_all('span', id="priceblock_ourprice")):
			tempPrice = bs.find_all('span', id="priceblock_ourprice")
		else:
			tempPrice = bs.find_all('span', id="priceblock_dealprice")
		regTempTitle = re.search(r'>[\s\S]*.*</span>',str(tempTitle))
		regTempPrice = re.search(r'￥.*\d*',str(tempPrice))
		#print(tempTitle+tempPrice)
		#print(regTempTitle.group()+regTempPrice.group())
		if bool(regTempTitle):
			regTempTitleStr = regTempTitle.group().strip(">").strip("</span>")
			regTempTitleStr = re.sub(r'[\s\n]+', "", regTempTitleStr)
			productDetailsList.append(regTempTitleStr)
			print(regTempTitleStr)
		if bool(regTempPrice):
			regTempPriceStr = regTempPrice.group().strip("</span>]")
			productDetailsList.append(regTempPriceStr)
			print(regTempPriceStr)
		productDetailsList.append("https://www.amazon.co.jp/dp/"+tempProduct)
	print(productDetailsList)

def access_Product():
	for tempProductDetails in productDetailsList:
		print(tempProductDetails)

def view_Product():
	for tempProduct in productListDiff:
		print("https://www.amazon.co.jp/dp/"+tempProduct)
	### 最終出力を吐いたら配列は全クリアにする。
	global productListPast
	productListPast = list(productList)
	productList.clear()

### おまじない
main()
