-- CreateTable
CREATE TABLE "Team" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL,
    "elo" INTEGER
);

-- CreateTable
CREATE TABLE "Match" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "date" TEXT NOT NULL,
    "teamAName" TEXT NOT NULL,
    "teamBName" TEXT NOT NULL,
    "p1" REAL,
    "pX" REAL,
    "p2" REAL,
    "bttsSi" REAL,
    "golesOver25" REAL,
    "cornersOver95" REAL,
    "scoreA" INTEGER,
    "scoreB" INTEGER,
    "settled" BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT "Match_teamAName_fkey" FOREIGN KEY ("teamAName") REFERENCES "Team" ("name") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Match_teamBName_fkey" FOREIGN KEY ("teamBName") REFERENCES "Team" ("name") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Market" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "matchId" TEXT NOT NULL,
    "mercado" TEXT NOT NULL,
    "ambito" TEXT NOT NULL,
    "evento" TEXT NOT NULL,
    "linea" TEXT NOT NULL,
    "probabilidad" REAL NOT NULL,
    CONSTRAINT "Market_matchId_fkey" FOREIGN KEY ("matchId") REFERENCES "Match" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "Team_name_key" ON "Team"("name");

-- CreateIndex
CREATE INDEX "Match_date_idx" ON "Match"("date");

-- CreateIndex
CREATE INDEX "Market_matchId_mercado_idx" ON "Market"("matchId", "mercado");
