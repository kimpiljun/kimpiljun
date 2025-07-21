# 🎮 LoL MMR 게임 영향력 모델링 프로젝트

<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white"/> <img src="https://img.shields.io/badge/R-276DC3?style=for-the-badge&logo=R&logoColor=white"/> <img src="https://img.shields.io/badge/SQL-4479A1?style=for-the-badge&logo=MySQL&logoColor=white"/> <img src="https://img.shields.io/badge/LoL%20API-5C2D91?style=for-the-badge&logo=riot-games&logoColor=white"/>

이 프로젝트는 단순한 승패 결과가 아닌, 실제 **게임 내 퍼포먼스**를 기반으로 한 리그 오브 레전드(LoL)의 맞춤형 MMR(Matchmaking Rating) 시스템을 구축하는 것을 목표로 합니다. 상세한 전적 데이터를 분석하여 각 플레이어의 영향력을 수치화하고, 이를 기반으로 부정 행위자 탐지, 공정한 매칭, 대회 선발 등에 활용할 수 있는 정교한 점수 체계를 설계합니다.

---

## 🎯 목표

✅ 단순 승패가 아닌 **기여도 기반 평가**로 더 정교한 MMR 점수 체계 제공
✅ **치트/스머프 사용자 탐지**로 매칭 공정성 향상
✅ **팀 구성의 질적 향상**을 위한 평가 시스템 구축

---

## 📂 데이터 및 도구

* **데이터 출처**: 공개된 LoL 전적 로그 + 자체 라벨링 데이터
* **주요 변수**: 킬, 어시스트, 딜량, 골드, 시야 점수, 오브젝트 기여도 등
* **사용 도구**:
  `Python`, `R`, `SQL`, `pandas`, `scikit-learn`, `seaborn`, `matplotlib`

---

## 📊 분석 방법론

1. **Game Impact Score 계산**: 각 플레이어의 퍼포먼스를 정규화된 지표로 수치화
2. **이상치 탐지**: RandomForestClassifier로 부정 사용자 탐지
3. **군집 분석**: 유사한 기여도 유형의 플레이어 그룹화
4. **MMR 조정 로직 설계**

   * ⬆️ 패배했지만 활약도가 높은 경우 → 가산점
   * ⬇️ 승리했지만 기여도가 낮은 경우 → 감점
   * ➖ 평균적인 기여도 → 점수 유지

---

## 🔍 주요 특징

✨ **포지션별 정규화**로 공정한 비교 가능
✨ **스코어 0\~100 정량화**로 직관적인 영향력 파악
✨ **이상 사용자(치터/스머프)** 탐지 기능 내장
✨ **시각화 기반 분석 리포트** 동봉 (PDF 포함)

---

## 📁 프로젝트 구조

```
MMR_project/
│
├── data/               # 전처리된 매치 로그 및 원본 데이터
├── eda/                # 변수 분포 및 영향력 분석
├── modeling/           # 분류기 및 점수 계산 모델 코드
├── MMR_report.pdf      # 전체 리포트 및 시각화 결과
└── README.md           # 프로젝트 설명 문서
```

---

## 📌 활용 사례

* 🎯 **스머프/치터 탐지**: 부정 행위 여부 조기 판별 가능
* 🏆 **대회 운영 최적화**: 실제 기여도 기반 선발 기준 마련
* ⚙️ **매칭 시스템 고도화**: 커뮤니티 또는 서버 운영 시 활용 가능

---

## 🧑‍💻 작성자

**김필준 (Piljun Kim)**
📧 [kimpj1997@naver.com](mailto:kimpj1997@naver.com)
🔗 [Notion 포트폴리오 보기](https://notion.so/abbb0b673a594e5899f3ad4a2880e666)

---

> *“모든 승리가 같지 않듯, 우리는 팀 게임에서 진짜 중요한 것을 측정할 수 있어야 합니다.”*
