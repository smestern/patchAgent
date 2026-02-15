## What is this?

The current advent of AI-for-Science is really promising. I was initially skeptical on AI in general, but I have recently come around in using AI for refinement, as a sort of bounce off point. 
The current AI-for-science tools focus primarily on two things:   
- Literature search & review
- End-to-End experimental pipelines
While these tools are great, and will help advance the field greatly. I think there is a gap that still exists. 
To me, there is an intermediate step where Agentic AI could really help. That is, in the space of producing robust and scientifically rigorous research code in a human-in-the-loop manner.
In the life sciences space, many researchers come from a background with little to no programming experience. They often can run a few python scripts or setup a conda env, but beyond that it plateaus. Most life science researchers generally don't need the AI to run end-to-end research for them.

Moreover, often researchers have a special, novel idea, for feature engineering or something, that a prebuilt e2e pipeline will not. The researchers know what problem they want to solve, but designing a rigorous and reproducible scientific code

I tried prototyping out some tools that I think could really help in the form of [sciagent](https://github.com/smestern/sciagent).