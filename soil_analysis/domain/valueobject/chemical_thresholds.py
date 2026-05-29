"""
化学分析の判定閾値定義
川田研究所の「化学分析結果の見方」に基づく基準
"""

# pH (水素イオン濃度)
PH_LOW = 6.0
PH_HIGH = 7.0

# EC (電気伝導率) mS/cm
EC_LOW = 0.1
EC_HIGH = 0.5

# アンモニア態窒素 (NH4-N) mg/100g
NH4N_UPPER_LIMIT = 5.0

# 硝酸態窒素 (NO3-N) mg/100g
NO3N_UPPER_LIMIT = 15.0

# 腐植 (%)
HUMUS_LOW = 3.0

# 塩基飽和度 (%)
BASE_SATURATION_LOWER_LIMIT = 60.0
BASE_SATURATION_UPPER_LIMIT = 80.0
BASE_SATURATION_OVER_LIMIT = 100.0

# 可給態リン酸 (P2O5) mg/100g
P2O5_LOW = 10.0
P2O5_HIGH = 30.0

# 塩基置換容量 (CEC) meq/100g
CEC_LOW = 12.0
