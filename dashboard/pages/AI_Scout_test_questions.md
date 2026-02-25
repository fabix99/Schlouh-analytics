# AI Scout — Test Questions (~100)

Use these to test the chatbot across the full scope of the data. Copy-paste into the AI Scout chat, then review answers to decide what to tweak (RAG, prompts, or context).

---

## Basic — Goals, assists, rating

1. Who has the most goals in the database?
2. Who has the most assists?
3. Who has the best average rating?
4. Who is the top goalscorer in the current season?
5. Who has the most goals in the 2024/25 season?
6. Top 5 goalscorers in the Premier League last season?
7. Which player has the highest average rating in Serie A?
8. Who has more assists: Fernandinho or another midfielder in the data?

---

## Player — By position, minutes, appearances

9. Who are the best-performing forwards (by rating) in the data?
10. Which goalkeepers have the highest average rating?
11. Who played the most minutes in the 2023/24 season?
12. Which players have at least 20 appearances in a single season?
13. Who has the most appearances in the database?
14. Best-rated defender in the Premier League?
15. Which midfielders have the most goals in La Liga?

---

## Player — xG, xA, per90 (expected goals/assists)

16. Who has the highest expected goals per 90 (xG per 90) in the data?
17. Who has the highest expected assists per 90?
18. Which player outperforms his xG the most (goals vs expected goals)?
19. Who has the best xG per 90 in the current season?
20. List players with very high xA per 90.

---

## Player — Specific names and lookups

21. What are Cristiano Ronaldo's stats in the database?
22. Do you have data on Mohamed Salah?
23. Which team does [pick a player name from your data] play for?
24. In which leagues and seasons do we have data for Fernandinho?
25. What is the average rating of [specific player] in 2023/24?

---

## Team — Season stats, xG, matches

26. Which team has the most goals (xG) for in a single season?
27. Which team has the best xG difference (xG for minus xG against) in a season?
28. How many matches did [team name] play in the 2024/25 season?
29. Do we have team-level data? What team stats are available?
30. Which teams have the highest xG for in the Premier League?
31. What is the xG for and xG against for [specific team] in 2023/24?
32. How many different teams do we have in the database?

---

## Team — Existence and coverage

33. Do you have data on Liverpool?
34. Which leagues do we have team data for?
35. List some teams from the Bundesliga.
36. What team aspects or team stats can you tell me about?

---

## Matches — Results, scores, dates

37. What was the score in the last match between [team A] and [team B]?
38. How many matches do we have in the database?
39. What are the biggest wins (highest goal difference) in the data?
40. Do we have match results for the 2024/25 season?
41. Which match had the most goals (total home + away)?
42. List some recent match results for the Premier League.
43. What was the xG in the match [home team] vs [away team]?

---

## Matches — By competition and round

44. How many Premier League matches do we have per season?
45. Which competition has the most matches in the database?
46. Do we have round or matchday information for fixtures?

---

## League / competition — Coverage and aggregates

47. Which leagues (competitions) are in the database?
48. Which seasons do we have for the Premier League?
49. How many players do we have per competition?
50. What is the total number of goals in the Premier League 2023/24?
51. Average team xG for in La Liga last season?
52. Which competition has the highest average player rating?

---

## Comparisons — Two players or two teams

53. Compare the goals of the top two goalscorers in the data.
54. Who has more assists, [player A] or [player B]?
55. Which team has a better xG difference: [team A] or [team B] in the same season?
56. Compare average ratings of two players in the same league and season.

---

## Time and season — Current, latest, specific

57. What is the latest season we have in the database?
58. Do we have data for the 2025/26 season?
59. Who is the top goalscorer right now (current season)?
60. What seasons are available for the Champions League?
61. Is the 2022/23 season fully covered?

---

## Edge cases — Data availability and limits

62. Do you have data on [obscure player or team]?
63. What data do you not have? What are your limitations?
64. Can you tell me about red cards or yellow cards?
65. Do we have possession or shot statistics?
66. Is there data on managers or coaches?
67. Do we have injury or availability data?
68. What player stats besides goals, assists, and rating are available?

---

## Aggregations and rankings

69. Who are the top 10 goalscorers across all seasons and leagues?
70. Which league has the most total goals in the data?
71. What is the average number of goals per player per season in the database?
72. How many players have scored more than 10 goals in a season?
73. Which season had the highest total goals in the database?
74. Top 5 players by total minutes played.

---

## Advanced — Ratios, differences, “best” by criteria

75. Who has the best ratio of goals to expected goals (overperformance)?
76. Which player has the most goal contributions (goals + assists) in a single season?
77. Best average rating among players with at least 1000 minutes?
78. Which team conceded the fewest xG in a season (if we have xG against)?
79. Who leads in assists per 90 (if derivable from our data)?
80. Top forwards by both goals and xG per 90.

---

## Conjunctive and multi-part questions

81. Who has the most goals in the Premier League in the 2023/24 season?
82. Best-rated player in Serie A with at least 15 appearances?
83. Which team in La Liga had the highest xG for in 2024/25?
84. Top 3 goalscorers in the current season in the top 5 leagues.
85. Compare the top goalscorer and top assister in the same league and season.

---

## Discovery and schema

86. What tables or types of data do you have?
87. What can I ask you? What questions can you answer?
88. Do you have data on transfers or market values?
89. Can you list all competitions you know?
90. What does “competition_slug” mean in your data?
91. What is the structure of your player stats?

---

## Stress and phrasing

92. goals top scorer premier league 2024
93. best player rating
94. team xG stats
95. most assists current season
96. who scored the most goals ever in your data
97. give me the top 5 strikers by goals in la liga 2023-24
98. do we have 2025/2026 season
99. which league has most matches
100. summarize what football data you have in one paragraph

---

*Tip: Run the app, open AI Scout, and go through these in batches. Note which answers are wrong, missing, or verbose, then adjust RAG (which context we fetch), the system prompt, or add targeted priority context for the intents that fail.*
