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
**Problem 1.** Hallucinations / Fakery at critical points. I noticed agentic AI will often write scripts that analyze "idealized data" or will simply make up data to pass tests. Sometimes it will essentially [p-hack](https://en.wikipedia.org/wiki/Data_dredging) for the researcher
**Problem 2.** Domain specific knowledge gaps. Researchers (myself included) will often use jargon-y terms, and require the use of domain-specific tools. There are gaps in the generalized background knowledge of most models and they likely do not have specific specialized libraries memorized.

I tried prototyping out some tools that I think could really help in the form of [sciagent](https://github.com/smestern/sciagent). This essentially is a framework for introducing scientific rigor and domain specific tools to agentic AI. 
The rigor reinforcements attempt to solve **problem 1**, by reminding the AI to not just make stuff up, and to double and triple check its code and the data. For **problem 2** domain specific tools, I included structure for scientists to codify their domain specific knowledge. Also space for definie domain specific software packages that the scientist may want to use in their work. There is also an attempt at a novice friendly wizard that attempts to self assemble an agent for you.

## Example: PatchAgent
*See: [What is Patch-Clamp Electrophysiology?](01-what-is-patch-clamp.md)*  

My day-job field is [patch-clamp electrophysiology](https://en.wikipedia.org/wiki/Patch_clamp) (in particular whole-cell patch clamp). This is a specialized technique in which neuroscientists can record signals from individual neurons in a highly targeted manner. Using this technique, we can see what individual neurons are doing across the brain.

Patch clamp signals are highly patterned time series. There are a number of features & events one can see in a standard action potential. Of particular note here, are [action potentials (or spikes)](https://en.wikipedia.org/wiki/Action_potential), essentially the primairy mechenism of signal propagation within a neuron. When and how action potentials occur tells us a lot about how a neuron ingests and transforms an incoming signal. 
<img src="ic1_sweep_details.png" alt="Current clamp sweeps from a single neuron" width="25%"/>
*Image: The voltage response of a single neuron. Sweep 3 and onwards shows large voltage deviations that are action potentials*

For this example, we will be asking the agent to detect action potentials from neurons across three different conditions. More specificaly, we want to analyze the F-I curve (Frequency - Injection). Eg, how the frequency of action potentials evolves with increasing stimulation

![main](img_1.png) 
*Image: Left, The primairy CLI entry point for patch-agent*

Here we point the agent towards the files. Tell it in general, what protocol to look for, and what we want to do. Notably the files are all in the [propriatery `ABF` format](https://swharden.com/pyabf/abf2-file-format/). SWHarden has an amazing python package for opening these files - but general coding agents fail to reliably invoke it.

![first_analysis](img_2.png)  
<img src="fi_curves_ic1.png" alt="FI curves single sweep" width="50%"/>

The first pass analysis works quite well. 