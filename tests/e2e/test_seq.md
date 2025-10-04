# 테스트 순저

## UI로드
- playwright를 통해 UI를 띄움.

## 파일 업로드
- '/Users/cjlee/Documents/Python/test_MedDRA_AutoInput/Raw_Data/MedDRA_________100__.csv'파일 업로드

## 입력수행
1) 로딩된 화일의 현재 행의 데이터를 가져와서 필드에 입펵. 초기값은 0번 행력이고, 한번 수행시 마다 1 추가.
2) '증상 저장하기' 버튼을 실행하여 DB에 저장.
3) 파일 내의 자료가 모두 입력될 때 까지 반복.
4) 진핸과정은 모두 playwright에서 사용자에거 보여줄 것.