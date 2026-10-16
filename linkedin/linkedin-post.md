A small server under my desk now writes our family newsletter. No cloud account, no API key, no subscription.

At 6 a.m. it wakes up, researches the news, and has an issue on the home network before anyone is out of bed. The hardware is a Ryzen 9 with 32 GB of RAM and no graphics card. Ollama runs Qwen3 30B-A3B, a mixture-of-experts model that uses only about 3B parameters per token, so a plain CPU keeps up. A Python agent of roughly 650 lines lets the model search the web and read pages, then turns what it finds into stories. nginx serves them to every phone and laptop in the house. Search queries are the only thing that leaves.

My favourite part is one rule in the code: a story gets published only if its source is a page the agent actually opened. The model can sound as confident as it likes. Cite a link it never visited, and the story is dropped. Judge the output by its evidence, not its tone. I'd hold people to the same standard.

Tailoring it takes one config file: topics, tone, reading level, model. Ours covers local news, tech and AI, and the trails. Yours could be a hockey team, a book club, or grandparents who want the week in plain language.

Was there a "turn it off and on again" moment? Of course. Twenty years in enterprise IT, and the oldest fix still works.

Useful AI doesn't need a data centre. It needs a small box, a clear job, and a rule about evidence.

#LocalAI #Ollama #HomeLab
