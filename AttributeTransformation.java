public abstract class AttributeTransformation {

    //returns the appropriate attribute transformation enum
    public abstract AttributeTransformationType getType();

    public boolean structurallyEqual(AttributeTransformation o) {
        return getType() == o.getType() && subclassStructurallyEqual(o);
    }

    protected abstract boolean subclassStructurallyEqual(AttributeTransformation o);

    public enum AttributeTransformationType {
        NoChange(7),
        Reflection(6),
        Rotation(5),
        FillChange(4),
        Scale(3),
        AlignmentChange(2),
        ShapeChange(1),
        Creation(0),
        Deletion(0);

        public int getBaseWeight() {
            return baseWeight;
        }

        private int baseWeight;

        AttributeTransformationType(int baseWeight) {
            this.baseWeight = baseWeight;
        }

    }
}