# AI Scout — Test Questions v2 (100 new questions)

Second set of questions to test the chatbot. Use with the test runner or paste into the AI Scout chat.

---

## Basic — Goals, assists, rating

1. Who is the leading goalscorer across all competitions in your data?
2. Name the player with the highest total assists in the database.
3. Which player has the best average rating (minimum minutes played)?
4. Top goalscorer in the latest season you have?
5. Who scored the most goals in 2023/24?
6. Give me the top 5 assist providers in the Premier League.
7. Highest-rated player in La Liga?
8. Compare total goals for the top 3 goalscorers in the data.

---

## Player — Position, minutes, appearances

9. Best-performing strikers by average rating?
10. Which goalkeepers have the best ratings in the database?
11. Who accumulated the most minutes in a single season?
12. List players with 15 or more appearances in one season.
13. Who has the highest number of appearances overall?
14. Best-rated centre-back or defender in the data?
15. Which midfielders scored the most goals in the Bundesliga?

---

## Player — xG, xA, expected metrics

16. Who has the highest xG per 90 in your records?
17. Top 5 players by expected assists per 90?
18. Which player has the biggest positive difference between goals and xG?
19. Best xG per 90 in the current or latest season?
20. Name players with very high expected assists per 90.

---

## Player — Specific lookups and names

21. What stats do you have for Bruno Fernandes?
22. Do you have any data on Erling Haaland?
23. Which team does the top goalscorer in your data play for?
24. Which competitions and seasons do we have for Kevin De Bruyne?
25. What was the average rating of the top assister in 2023/24?

---

## Team — Season stats and xG

26. Which team has the highest total xG for in one season?
27. Best xG difference (for minus against) in a single season?
28. How many matches did Manchester City play in 2023/24?
29. What team-level statistics are available in the database?
30. Top 5 teams by xG for in La Liga?
31. xG for and xG against for Chelsea in the latest season?
32. How many unique teams appear in the database?

---

## Team — Coverage and existence

33. Do you have data on Arsenal?
34. Which competitions have team data?
35. List a few teams from Serie A.
36. What can you tell me about team stats or team-level data?

---

## Matches — Results and scores

37. What was the result of the last meeting between two specific teams in your data?
38. Total number of matches in the database?
39. Which matches had the largest goal difference (biggest wins)?
40. Are there match results for 2023/24?
41. Which fixture had the most goals (home + away combined)?
42. Show some Premier League match results.
43. What was the xG in a specific high-scoring match?

---

## Matches — Competition and round

44. How many La Liga matches do you have per season?
45. Which competition has the highest match count?
46. Do you have matchday or round information for games?

---

## League / competition — Coverage and aggregates

47. List all leagues or competitions in the database.
48. Which seasons do you have for La Liga?
49. How many player-season records per competition?
50. Total goals scored in the Premier League in the latest season?
51. Average team xG for in the Bundesliga last season?
52. Which league has the highest average player rating?

---

## Comparisons — Players or teams

53. Compare goals for the top two assist providers.
54. Who has more goals: the top goalscorer or the second?
55. Which of two given teams has the better xG difference in the same season?
56. Compare the ratings of the top goalscorer and top assister in one league.

---

## Time and season — Latest, current, specific

57. What is the most recent season in the database?
58. Do we have 2024/25 season data?
59. Who is the current season’s top goalscorer?
60. What seasons are available for the Bundesliga?
61. Is 2023/24 fully covered in your data?

---

## Edge cases — Limits and availability

62. Do you have data on a very obscure player or lower-league team?
63. What are your data limitations?
64. Can you provide red or yellow card stats?
65. Do you have possession or shot data?
66. Is there any manager or coach data?
67. Do you have injury or availability information?
68. Which player statistics (beyond goals, assists, rating) are available?

---

## Aggregations and rankings

69. Top 10 goalscorers of all time in your data?
70. Which competition has the most total goals?
71. Average goals per player per season in the database?
72. How many players have scored 15+ goals in a season?
73. Which season had the most total goals?
74. Top 5 by total minutes played.

---

## Advanced — Ratios and “best” by criteria

75. Who overperforms xG the most (goals minus xG)?
76. Most goal contributions (goals + assists) in one season?
77. Best average rating with at least 900 minutes played?
78. Which team had the lowest xG against in a season?
79. Who has the best assists per 90 in the data?
80. Top attackers by both goals and xG per 90.

---

## Conjunctive and multi-part

81. Who has the most goals in La Liga in 2023/24?
82. Best-rated player in the Premier League with at least 20 appearances?
83. Which Serie A team had the highest xG for in the latest season?
84. Top 3 goalscorers in the current season across the main leagues.
85. Compare the top goalscorer and top assister in the same competition and season.

---

## Discovery and schema

86. What kinds of data or tables do you have?
87. What types of questions can you answer?
88. Do you have transfer or market value data?
89. List all competitions in the database.
90. What does competition_slug represent?
91. Describe the structure of your player statistics.

---

## Stress and phrasing (informal or terse)

92. top scorer goals premier league
93. best rating player
94. team xG
95. assists this season
96. most goals all time in database
97. top 5 strikers goals la liga
98. 2024/25 season available?
99. league with most games
100. one paragraph summary of your football data

---

*Tip: Run with the test script (`python dashboard/pages/run_ai_scout_tests.py`) or paste into AI Scout in batches. Use results to refine RAG, prompts, or priority context.*
