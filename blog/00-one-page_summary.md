## What is this?

The current advent of AI-for-Science is really promising. I was initially skeptical on AI in general, but I have recently come around in using AI for refinement, as a sort of bounce off point. 
To me, there is an intermediate step where Agentic AI could really help that is failed to be considered.  

That is, in the space of producing robust and scientifically rigorous research code in a human-in-the-loop manner. In the life sciences space, many researchers come from a background with little to no programming experience. They often can run a few python scripts or setup a conda env, but beyond that it plateaus. They often have complex analyses that they want to run on their data, but lack the programming expertise to generate research code to achieve that. 

The current AI-for-science tools focus primarily on two things:   
- Literature search & review
- End-to-End experimental pipelines (LLM does question->hypothesis->)
While these tools are great, and will help advance the field greatly.

Most life science researchers generally don't need the AI to run end-to-end research for them. Moreover, most researchers don't have a lack of questions, we actualy have too many questions and hypotheses. Where the assistence comes in, is helping life science researchers design and run experiemental code (also wet-lab automation in the near-future would also be super helpful! but thats a whole 'nother topic). 

With that in mind, agentic AI coding seems to revolutionalize this. Researchers can now build complex code with really simple basic-language instructions. However, in my work, I notice that default agentic AI falls flat in two specific ways:
1. Hallucinations / Faker-y at critical points. I noticed agentic AI will often write scripts that analyze "idealized data" or will simply make up data to pass tests. 
2. Domain specific knowledge gaps. Researchers (myself included) will often use jargon-y terms, and require the use of domain-specific tools

I tried prototyping out some tools that I think could really help in the form of [sciagent](https://github.com/smestern/sciagent). This essentially is a framework for introducing scientific rigor and domain specific tools to agentic AI. 

##