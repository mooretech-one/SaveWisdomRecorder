# SAVEWISDOM RECORDER

The concept of savewisdom.org is worthy of promotion, because answering 
the 1000 questions not only brings you better knowledge of self, but 
also builds the basis for training your own AI.

But lack of translation makes the list useless for elderly people who
never learned English, and hardly know how to use technology. And 
since their wisdom is even more important, it was useful to create 
something to assist them. 

And so, a few hours with Grok was enough to create something clean and
simple to remedy the situation.

## Overview

The SaveWisdomRecorder consists of two parts, since the recording part 
needs to be fully offline, but retrieving and translating the questions
can be more easily done on a connected system.

The GitHub repository has a WorkFlow to build versions for Windows, 
MacOS, and Linux. The program can even be run from a USB stick, allowing 
you to take it from computer to computer. 

### prepare_question.py

This script takes a single parameter, that is either a country code, 
or a language as present in the Google Translate language names set. 
If two characters in size it is considered a country code, but this is 
somewhat less useful: many countries are considered to have English 
as language, and so the questions won't be translated.

A better option is the use of a language, like German, Simplified 
Chinese, or others. All words following as command line parameters are 
considered to form the name of one language. 

The script then downloads the original English list of questions from
savewisdom.org, and uses Google Translate to translate it to the desired
language. The translation file is then added to the QUESTIONS folder
as questions_{country_code}.json.

### save_wisdom_recorder.py

The second part is the GUI application which uses the translated questions.
It is fully offline, and only uses question files that are locally
available. 

When started, the user needs to enter a name and select one of the 
available languages, and then click Select. This prepares the program for 
use for this one user. 

Once Select was clicked, the first unanswered question for the selected
user is shown. The user can think about what to answer, click record and 
dictate their answer. When done speaking, Stop, Random, or next can be 
clicked. When the MP3 file has been stored, the next question is shown.

