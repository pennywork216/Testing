from collections import defaultdict

from nltk import ConditionalFreqDist
from textblob import Word

import Utils
from KnowledgeBank import KnowledgeBank
from Ontology import Dictionary


class Evaluator:
    def __init__(self):
        self.knowledge_bank = KnowledgeBank()
        self.evaluation_bank = {}
        # used to identify the category to put the query in if feedback is correct
        self.category_bank = {}
        # used to identify the wordpair to increase/decrease score based on feedback
        self.id_to_wordpair_dict = {}
        self.id_to_matchedwords_dict = {}
        return

    # return best_faq_id, category, matched word_pairs
    def evaluate(self, lemmatized_question):
        score_bank = defaultdict(int)
        slot, categories = self.knowledge_bank.classify_question(lemmatized_question)
        key_words = set([w for w in lemmatized_question if w[0] not in Utils.stop_words])
        # print("msg:", msg)
        # print("Categories:", [c.keyword for c in categories])
        for category in categories:
            # conduct word matching and put results into evaluation bank
            self._evaluate_by_word(key_words, category, slot)
        for word_tag, question_scores in self.evaluation_bank.items():
            for question_score in question_scores:
                related_question_id = question_score[0]
                similarity_score = question_score[1]
                category = question_score[2]
                # print(key, related_question, similarity_score, total_score)
                score_bank[related_question_id] += similarity_score
                # todo: what happen if map multiple category?
                self.category_bank[related_question_id] = category
        if not score_bank:
            return -1, self.knowledge_bank.get_or_set_category(Dictionary.default), []
        best_faq_id = max(score_bank, key=score_bank.get)
        num_of_nouns = len(set([x for x in lemmatized_question if x[1] == "N"]))
        best_score = score_bank[best_faq_id] if num_of_nouns == 0 else score_bank[best_faq_id]/num_of_nouns
        # best_score = score_bank[best_faq_id]/ (len(lemmatized_question)*1.0)
        if category.keyword == Dictionary.default:
            threshold = 1
        else:
            threshold = 0.6
        if best_score <= threshold:
            # only matched one similar word
            return -1, self.knowledge_bank.get_or_set_category(Dictionary.default), []
        word_pairs = self.id_to_wordpair_dict.get(best_faq_id, [])
        return best_faq_id, self.category_bank[best_faq_id], word_pairs

    # find matches for each word
    def _evaluate_by_word(self, query, category, slot):
        word_bank = self._find_word_bank(category, slot)
        for word_tag in query:
            word = word_tag[0]
            tag = word_tag[1]
            if word_tag in word_bank:
                self._handle_exact_word_match(category, word_bank, word_tag)
            elif tag[0] in Utils.tags and word not in Utils.domain_specific_words:
                self._handle_similar_word_match(category, word_bank, word_tag)
                # add to list of matched words
        return

    def _handle_similar_word_match(self, category, word_bank, word_tag):
        # no exact match of word, either use Wordnet's synset,
        #  or see if the similarity score already exists in knowledge base from past synset evaluation
        # only match word once for each question
        best_match_words, best_similarity_score = self._get_best_word_matches(word_bank, word_tag)
        matched_question = []
        for best_match_word_tag in best_match_words:
            # there was a best match, retrieve CFD that contains FAQs which have that syn
            # self.evaluation_bank[best_match_word] = []
            for related_question_id in word_bank[best_match_word_tag].keys():
                if related_question_id not in matched_question:
                    matched_question.append(related_question_id)
                    score = word_bank[best_match_word_tag][related_question_id]
                    # associate qid to matched word pair for feedback later
                    self.id_to_wordpair_dict.setdefault(related_question_id, []).append((word_tag, best_match_word_tag))
                    # make similarity score reduce a bit, prefer exact match
                    self.evaluation_bank.setdefault(best_match_word_tag, []).append(
                        [related_question_id, score * best_similarity_score * 0.8, category])

    def _get_best_word_matches(self, word_bank, word_tag):
        word = Word(word_tag[0])
        tag = word_tag[1]
        syn_sets_with_tag = word.get_synsets(pos=Utils.tags[tag[0]])
        syn_sets_wo_tag = word.get_synsets()
        best_similarity_score = 0.2
        best_match_words = []
        for related_word_tag in word_bank:
            # related_word = related_word_tag[0]
            related_tag = related_word_tag[1]
            if related_tag[0] in Utils.tags:
                # if similarity has been calculated previously, pull out similarity score
                similarity_score = self.knowledge_bank.instance.word_pair_similarity.setdefault(frozenset((word_tag,
                                                                                                           related_word_tag)),
                                                                                                self._calculate_similarity(
                                                                                                    related_word_tag,
                                                                                                    syn_sets_with_tag,
                                                                                                    syn_sets_wo_tag))
                if similarity_score >= best_similarity_score:
                    if similarity_score > best_similarity_score:
                        best_similarity_score = similarity_score
                        best_match_words = []
                    best_match_words.append(related_word_tag)
        return best_match_words, best_similarity_score

    def _calculate_similarity(self, related_word_tag, syn_sets_with_tag, syn_sets_wo_tag):
        ref_tb_word = Word(related_word_tag[0])
        related_tag = related_word_tag[1]
        ref_syn_sets = Dictionary.synset_map.get(ref_tb_word.lemmatize(), ref_tb_word.get_synsets(pos=Utils.tags[
            related_tag[0]]))
        similarity_score = self._get_path_similarity(syn_sets_with_tag, ref_syn_sets)
        # account for case where tagging is wrong
        # print(word_tag, related_word_tag, similarity_score)
        if similarity_score == 0:
            # consider no tag
            similarity_score = self._get_path_similarity(syn_sets_wo_tag, ref_syn_sets)
        return similarity_score

    def _handle_exact_word_match(self, category, word_bank, word_tag):
        # an exact match is found
        for related_question_id in word_bank[word_tag].keys():
            score = word_bank[word_tag][related_question_id]
            # print(word, related_question, score)
            # print(key, score)
            self.evaluation_bank.setdefault(word_tag, []).append([related_question_id, score, category])
            # store matched words
            self.id_to_wordpair_dict.setdefault(related_question_id, []).append((word_tag, word_tag))
            # save into dict that maps word pair to similarity score
            # self.knowledge_bank.instance.word_pair_similarity[(word_tag, word_tag)] = 1

    def _find_word_bank(self, category, slot):
        if not slot:
            # an unknown interrogative word: go to the default slot
            word_bank = self.knowledge_bank.get_word_bank(category, "DEFAULT")
        else:
            # retrieve CFD from slot
            word_bank = self.knowledge_bank.get_word_bank(category, slot)
            current_category = category
            while not word_bank.conditions():
                # CFD is empty, explore the general roles
                general_role = current_category.get_general_role()
                if general_role:
                    current_category = general_role[0]
                    word_bank = self.knowledge_bank.get_word_bank(current_category, slot)
                else:
                    break
            current_categories = [category]
            while not word_bank.conditions():
                # CFD is still empty, explore the specific roles
                next_categories = []
                word_bank = ConditionalFreqDist()
                for current_category in current_categories:
                    specific_roles = current_category.get_specific_roles()
                    if specific_roles:
                        next_categories.extend(specific_roles)
                        for specific_role in specific_roles:
                            sub_bank = self.knowledge_bank.get_word_bank(specific_role, slot)
                            for word_tag in sub_bank:
                                for question in sub_bank[word_tag]:
                                    word_bank[word_tag][question] = sub_bank[word_tag][question]
                current_categories = next_categories
                if not current_categories:
                    break
            # can't find a specific or general role that could answer the question, go back to default slot of frame
            if not word_bank.conditions():
                word_bank = self.knowledge_bank.get_word_bank(category, "DEFAULT")
        return word_bank

    @staticmethod
    def _get_path_similarity(syn_sets, ref_syn_sets):
        max_sim = 0
        for syn_set_1 in syn_sets:
            for syn_set_2 in ref_syn_sets:
                sim = syn_set_1.path_similarity(syn_set_2)
                if sim and sim > max_sim:
                    max_sim = sim
        return max_sim

        # @staticmethod
        # def get_common_ngrams(questions, list_of_n):
        #     n_gram_dict = {}
        #     common_n_grams = {}
        #     for n in list_of_n:
        #         common_n_grams[n] = []
        #         for question in questions:
        #             n_grams = question.ngrams(n)  # List of WordList
        #             for n_gram in n_grams:
        #                 n_gram_string = ' '.join(n_gram)
        #                 if n_gram_string in n_gram_dict:
        #                     count = n_gram_dict[n_gram_string][1] + 1
        #                 else:
        #                     count = 1
        #                 n_gram_dict[n_gram_string] = [n_gram, count]
        #         for _, count in n_gram_dict.items():
        #             # only return n grams that occur more than 3 times
        #             if count[1] >= 3:
        #                 common_n_grams[n].append(count[0])
        #     return common_n_grams