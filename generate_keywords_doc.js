const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, HeadingLevel } = require("docx");

const NOISE_WORDS = [
  "noise", "noisy", "loud", "loudness", "roar", "roaring", "hum", "humming",
  "buzz", "buzzing", "drone", "droning", "rumble", "rumbling", "whine",
  "racket", "din", "blaring",
  "hear", "heard", "hearing", "sound", "sounds", "audible", "inaudible",
  "quiet", "silence", "deafening",
  "decibel", "dba", "db(a)", "db", "noise level", "sound level",
  "sound pressure", "low-frequency", "infrasound",
  "sleep disturbance", "sleep disruption", "insomnia", "migraine",
  "headache", "tinnitus", "annoyance", "stress",
  "noise ordinance", "noise regulation", "noise limit", "noise code",
  "noise complaint", "noise pollution", "noise control", "noise violation",
  "noise permit", "sound barrier", "sound wall",
];

const doc = new Document({
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    children: [
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        spacing: { after: 300 },
        children: [new TextRun({ text: "Noise Keywords", bold: true, font: "Arial", size: 32 })],
      }),
      ...NOISE_WORDS.map(word =>
        new Paragraph({
          spacing: { after: 60 },
          children: [new TextRun({ text: word, font: "Arial", size: 24 })],
        })
      ),
    ],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("Noise_Keyword_Reference.docx", buffer);
  console.log(`Done — ${NOISE_WORDS.length} words`);
});
